#!/bin/bash
set -e

OUTPUT_DIR="docs"
OUTPUT_FILE="$OUTPUT_DIR/baseline_TRL3.csv"
mkdir -p "$OUTPUT_DIR"
echo "run,timestamp,final_balance_kelly,final_balance_random,steps" > "$OUTPUT_FILE"

for i in {1..5}; do
    echo "Run $i..."
    RESULT=$(python3 mvp/cycle_demo.py 2>&1)
    # Берём строку, начинающуюся с "Kelly:"
    FINAL_LINE=$(echo "$RESULT" | grep '^Kelly:')
    # Извлекаем числа: всё, что после "Kelly: " и до " |", затем после "Random: "
    KELLY=$(echo "$FINAL_LINE" | sed -E 's/^Kelly: *([0-9.]+).*/\1/')
    RANDOM=$(echo "$FINAL_LINE" | sed -E 's/.*Random: *([0-9.]+).*/\1/')
    STEPS=$(echo "$RESULT" | grep -c '^Шаг')
    echo "$i,$(date -Iseconds),$KELLY,$RANDOM,$STEPS" >> "$OUTPUT_FILE"
    sleep 1
done

echo "Baseline measurements saved to $OUTPUT_FILE"
cat "$OUTPUT_FILE"