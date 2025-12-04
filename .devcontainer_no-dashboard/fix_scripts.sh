#!/bin/bash
# Fix the cd install-tl-* issue in both scripts

for DIR in direct-basic direct-medium; do
    echo "Fixing $DIR/setup.sh..."
    
    # Read the file and replace the problematic line
    awk '
        /^cd install-tl-\*/ {
            print "cd \"$(find . -maxdepth 1 -name \"install-tl-*\" -type d | head -1)\""
            next
        }
        { print }
    ' "$DIR/setup.sh" > "$DIR/setup.sh.tmp"
    
    mv "$DIR/setup.sh.tmp" "$DIR/setup.sh"
    chmod +x "$DIR/setup.sh"
    
    echo "✅ Fixed $DIR/setup.sh"
done

echo ""
echo "Verification:"
grep -n "cd.*install-tl" direct-basic/setup.sh direct-medium/setup.sh
