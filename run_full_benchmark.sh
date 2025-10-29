#!/bin/bash
# Full Benchmark Runner Script
# Automates the complete benchmark workflow on Jetson

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MODELS_DIR="models"
DATA_DIR="data"
RESULTS_DIR="results"
TEMPERATURE=0.0
MAX_TOKENS=1024
N_CTX=4096

# Function to print colored messages
print_msg() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Check if running on Jetson
check_jetson() {
    print_header "Checking Jetson Environment"

    if ! command -v tegrastats &> /dev/null; then
        print_error "tegrastats not found. Are you running on a Jetson device?"
        exit 1
    fi

    if ! command -v nvpmodel &> /dev/null; then
        print_error "nvpmodel not found. Are you running on a Jetson device?"
        exit 1
    fi

    print_msg "Jetson environment detected ✓"
}

# Set performance mode
set_performance_mode() {
    print_header "Setting Performance Mode"

    print_msg "Setting nvpmodel to max performance (mode 0)..."
    sudo nvpmodel -m 0

    print_msg "Locking clocks to maximum..."
    sudo jetson_clocks

    print_msg "Current nvpmodel settings:"
    sudo nvpmodel -q

    print_msg "Performance mode configured ✓"
}

# Check dependencies
check_dependencies() {
    print_header "Checking Dependencies"

    # Check Python version
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    print_msg "Python version: $python_version"

    # Check required packages
    required_packages=("llama_cpp" "pandas" "openpyxl" "requests")

    for package in "${required_packages[@]}"; do
        if python3 -c "import $package" 2>/dev/null; then
            print_msg "$package: installed ✓"
        else
            print_error "$package: NOT installed ✗"
            print_msg "Install with: pip3 install $package"
            exit 1
        fi
    done

    print_msg "All dependencies satisfied ✓"
}

# Check models exist
check_models() {
    print_header "Checking Models"

    if [ ! -d "$MODELS_DIR" ]; then
        print_error "Models directory not found: $MODELS_DIR"
        exit 1
    fi

    model_count=$(ls -1 "$MODELS_DIR"/*.gguf 2>/dev/null | wc -l)

    if [ "$model_count" -eq 0 ]; then
        print_error "No GGUF models found in $MODELS_DIR"
        print_msg "Please download models first (see JETSON_SETUP_README.md)"
        exit 1
    fi

    print_msg "Found $model_count model(s):"
    ls -1 "$MODELS_DIR"/*.gguf | while read -r model; do
        size=$(du -h "$model" | awk '{print $1}')
        print_msg "  - $(basename "$model") ($size)"
    done

    print_msg "Models ready ✓"
}

# Run inference benchmark
run_inference() {
    print_header "Running Inference Benchmark"

    # Create results directory
    mkdir -p "$RESULTS_DIR"

    # Get category from argument or prompt
    if [ -n "$1" ]; then
        category="$1"
    else
        print_msg "Available categories:"
        ls -1 "$DATA_DIR"/*_prompts_hierarchical.csv 2>/dev/null | while read -r file; do
            basename "$file" | sed 's/_prompts_hierarchical.csv//'
        done

        echo ""
        read -p "Enter category to benchmark (or 'all'): " category
    fi

    if [ "$category" = "all" ]; then
        # Run all categories
        for csv_file in "$DATA_DIR"/*_prompts_hierarchical.csv; do
            cat_name=$(basename "$csv_file" | sed 's/_prompts_hierarchical.csv//')
            print_msg "Benchmarking category: $cat_name"

            python3 run_llamacpp_collect.py \
                --models "$MODELS_DIR"/*.gguf \
                --prompts "$csv_file" \
                --out_jsonl "$RESULTS_DIR/runs_llamacpp_${cat_name}.jsonl" \
                --temperature "$TEMPERATURE" \
                --max_tokens "$MAX_TOKENS" \
                --n_ctx "$N_CTX"

            print_msg "Completed $cat_name ✓"
        done

        # Merge all results
        print_msg "Merging results..."
        cat "$RESULTS_DIR"/runs_llamacpp_*.jsonl > "$RESULTS_DIR/runs_llamacpp.jsonl"

    else
        # Run single category
        csv_file="$DATA_DIR/${category}_prompts_hierarchical.csv"

        if [ ! -f "$csv_file" ]; then
            print_error "Prompts file not found: $csv_file"
            exit 1
        fi

        print_msg "Benchmarking category: $category"

        python3 run_llamacpp_collect.py \
            --models "$MODELS_DIR"/*.gguf \
            --prompts "$csv_file" \
            --out_jsonl "$RESULTS_DIR/runs_llamacpp.jsonl" \
            --temperature "$TEMPERATURE" \
            --max_tokens "$MAX_TOKENS" \
            --n_ctx "$N_CTX"
    fi

    print_msg "Inference benchmark complete ✓"

    # Auto-export responses for easy review
    print_msg "Exporting responses to readable formats..."
    python3 export_responses.py --runs "$RESULTS_DIR/runs_llamacpp.jsonl" --all
    print_msg "Responses exported to: exported_responses/ ✓"
}

# Run quality evaluation
run_judging() {
    print_header "Running Quality Evaluation (Absolute Scoring)"

    # Check if API key is set
    if [ -z "$OPENAI_API_KEY" ]; then
        print_warning "OPENAI_API_KEY not set"
        read -p "Enter API key: " api_key
        export OPENAI_API_KEY="$api_key"
    fi

    # Get API URL
    read -p "API URL (default: https://api.openai.com/v1/chat/completions): " api_url
    api_url=${api_url:-https://api.openai.com/v1/chat/completions}

    # Get judge model
    read -p "Judge model (default: gpt-4o): " judge_model
    judge_model=${judge_model:-gpt-4o}

    print_msg "Running LLM-as-Judge evaluation (absolute scoring)..."
    print_msg "This scores each output 0-10 (faster & cheaper than pairwise)"

    python3 judge_absolute.py \
        --questions question.jsonl \
        --runs "$RESULTS_DIR/runs_llamacpp.jsonl" \
        --model "$judge_model" \
        --api_url "$api_url" \
        --api_key_env OPENAI_API_KEY \
        --out "$RESULTS_DIR/scores_absolute.csv"

    print_msg "Quality evaluation complete ✓"
}

# Aggregate results
aggregate_results() {
    print_header "Aggregating Results"

    python3 aggregate_to_excels_absolute.py \
        --runs "$RESULTS_DIR/runs_llamacpp.jsonl" \
        --scores "$RESULTS_DIR/scores_absolute.csv" \
        --outdir "$RESULTS_DIR"

    print_msg "Results aggregated ✓"
    print_msg "Output files:"
    ls -1 "$RESULTS_DIR"/*.xlsx 2>/dev/null | while read -r file; do
        print_msg "  - $(basename "$file")"
    done
}

# Main menu
show_menu() {
    print_header "Jetson Benchmark Runner"

    echo "Select an option:"
    echo "  1) Full benchmark (inference + judging + aggregation)"
    echo "  2) Inference only"
    echo "  3) Judging only (requires inference results)"
    echo "  4) Aggregation only (requires inference + judging)"
    echo "  5) Check environment"
    echo "  6) Exit"
    echo ""
    read -p "Enter choice [1-6]: " choice

    case $choice in
        1)
            check_jetson
            set_performance_mode
            check_dependencies
            check_models
            run_inference
            run_judging
            aggregate_results
            print_msg "Full benchmark complete! 🎉"
            ;;
        2)
            check_jetson
            set_performance_mode
            check_dependencies
            check_models
            run_inference
            print_msg "Inference complete! Run option 3 for judging."
            ;;
        3)
            if [ ! -f "$RESULTS_DIR/runs_llamacpp.jsonl" ]; then
                print_error "No inference results found. Run option 2 first."
                exit 1
            fi
            run_judging
            print_msg "Judging complete! Run option 4 for aggregation."
            ;;
        4)
            if [ ! -f "$RESULTS_DIR/runs_llamacpp.jsonl" ]; then
                print_error "No inference results found."
                exit 1
            fi
            if [ ! -f "$RESULTS_DIR/scores_absolute.csv" ]; then
                print_error "No judging results found. Run option 3 first."
                exit 1
            fi
            aggregate_results
            print_msg "Aggregation complete! 🎉"
            ;;
        5)
            check_jetson
            check_dependencies
            check_models
            print_msg "Environment check complete ✓"
            ;;
        6)
            print_msg "Exiting..."
            exit 0
            ;;
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
}

# Parse command line arguments
if [ $# -eq 0 ]; then
    # Interactive mode
    show_menu
else
    # Command line mode
    case $1 in
        full)
            check_jetson
            set_performance_mode
            check_dependencies
            check_models
            run_inference "$2"
            run_judging
            aggregate_results
            ;;
        inference)
            check_jetson
            set_performance_mode
            check_dependencies
            check_models
            run_inference "$2"
            ;;
        judge)
            run_judging
            ;;
        aggregate)
            aggregate_results
            ;;
        check)
            check_jetson
            check_dependencies
            check_models
            ;;
        *)
            echo "Usage: $0 [full|inference|judge|aggregate|check] [category]"
            echo ""
            echo "Commands:"
            echo "  full       - Run full benchmark"
            echo "  inference  - Run inference only"
            echo "  judge      - Run judging only"
            echo "  aggregate  - Aggregate results only"
            echo "  check      - Check environment"
            echo ""
            echo "Examples:"
            echo "  $0                    # Interactive mode"
            echo "  $0 full writing       # Full benchmark on writing category"
            echo "  $0 inference all      # Inference on all categories"
            echo "  $0 judge              # Judge existing results"
            exit 1
            ;;
    esac
fi
