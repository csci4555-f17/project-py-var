#!/bin/bash

cd "$(dirname "$0")"

TEST_SCRIPT_DIR='python'
ASSEMBLY_DIR='assembly'
EXECUTABLE_DIR='executable'

mkdir -p "$ASSEMBLY_DIR" "$EXECUTABLE_DIR"

for test in `ls $TEST_SCRIPT_DIR`; do

  test="${test%.py}"

  ../pyyc "$TEST_SCRIPT_DIR/$test.py" -o "$ASSEMBLY_DIR/$test.s"

  gcc -m32 -g -lm "$ASSEMBLY_DIR/$test.s" "../runtime/libpyyruntime.a" -o "$EXECUTABLE_DIR/$test"

done
