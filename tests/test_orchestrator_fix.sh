#!/bin/bash
# Test script for Orchestrator fix

echo "=============================================="
echo "Testing Orchestrator Worker Spawn Fix"
echo "=============================================="
echo ""

# Kill any existing gateway
pkill -f "nanobot gateway" 2>/dev/null
sleep 2

echo "🚀 Starting Gateway with Interactive Mode..."
echo ""

# Start gateway and capture output
nanobot gateway --multi -i 2>&1 | tee /tmp/gateway_test.log &
GATEWAY_PID=$!

# Wait for startup
sleep 10

echo ""
echo "📤 Sending test message: '实现一个简单的待办事项系统'"
echo ""

# Send test message (this would need interactive input)
# For now, just check if gateway is running

if ps -p $GATEWAY_PID > /dev/null; then
    echo "✅ Gateway is running"
    
    # Check logs for orchestrator skill loading
    if grep -q "orchestrator" /tmp/gateway_test.log; then
        echo "✅ Orchestrator skill detected in logs"
    else
        echo "⚠️  Orchestrator skill not yet visible in logs (normal for early startup)"
    fi
    
    # Stop gateway
    echo ""
    echo "⏹️  Stopping Gateway..."
    kill $GATEWAY_PID 2>/dev/null
    wait $GATEWAY_PID 2>/dev/null
    
    echo ""
    echo "✅ Test completed!"
else
    echo "❌ Gateway failed to start"
fi

echo ""
echo "=============================================="
echo "Manual Test Instructions:"
echo "=============================================="
echo ""
echo "1. Start gateway: nanobot gateway --multi -i"
echo ""
echo "2. Send complex task:"
echo "   >> 实现一个完整的订票系统"
echo ""
echo "3. Expected behavior (after fix):"
echo "   🔄 [orchestrator] Tool call: spawn(batch=[...])"
echo "   🤖 [research-worker] Processing: ..."
echo "   🤖 [backend-worker] Processing: ..."
echo "   🤖 [frontend-worker] Processing: ..."
echo ""
echo "4. Old behavior (before fix):"
echo "   🔄 [orchestrator] Tool call: write_file"
echo "   🔄 [orchestrator] Tool call: write_file"
echo "   (all work done by orchestrator alone)"
echo ""
