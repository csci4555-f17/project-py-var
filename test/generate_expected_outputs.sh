#!/bin/bash

cd "$(dirname "$0")"

TEST_SCRIPT_DIR='python'
INPUT_DIR='inputs'
EXP_OUT_DIR='expected_outputs'

for test in `ls $TEST_SCRIPT_DIR`; do

  if [[ $# -ne 0 && " $@" != *" ${test%.py}"* ]]; then
    continue
  fi

  test="${test%.py}"

  for test_file in `ls $INPUT_DIR/$test`; do

    echo "$test - $test_file"

    test_loc="$test/$test_file"

    mkdir -p "$EXP_OUT_DIR/$test"

    python <(cat "$TEST_SCRIPT_DIR/$test.py" | sed -re 's/input( *)\(( *)\)/int(input\1(\2))/g') < "$INPUT_DIR/$test_loc" > "$EXP_OUT_DIR/$test_loc"

  done

done
