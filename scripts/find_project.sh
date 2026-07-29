#!/bin/bash
# Find the Tank-robot project directory

echo "Searching for Tank-robot project..."

# Check common locations
for location in \
    "/opt/rock64-robot/Tank-robot" \
    "/opt/rock64-robot/tank-robot" \
    "/opt/rock64-robot/robot" \
    "/home/rock64/Tank-robot" \
    "/home/rock64/tank-robot" \
    "/home/rock64/robot" \
    "/mnt/c/Projects/Tank-Robot/Tank-robot" \
    "/mnt/c/Projects/Tank-Robot/tank-robot"; do
    
    if [ -d "$location" ]; then
        echo "✅ Found project at: $location"
        
        # Check if it has the expected structure
        if [ -f "$location/scripts/build_microros.sh" ]; then
            echo "✅ Confirmed: build_microros.sh found"
            echo "Run this command:"
            echo "  cd $location && bash scripts/build_microros.sh"
            exit 0
        else
            echo "⚠️  Directory exists but doesn't have expected structure"
        fi
    fi
done

# Search in home directory
echo "Searching in home directory..."
find ~/ -name "build_microros.sh" -type f 2>/dev/null | head -5

# Search in /opt
echo "Searching in /opt..."
find /opt -name "build_microros.sh" -type f 2>/dev/null | head -5

echo ""
echo "❌ Could not find Tank-robot project automatically"
echo ""
echo "Please navigate to your project directory manually:"
echo "  cd /path/to/your/Tank-robot"
echo ""
echo "Then run:"
echo "  bash scripts/build_microros.sh"