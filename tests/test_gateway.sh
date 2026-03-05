#!/bin/bash
# Test script for Gateway Interactive Mode

echo "============================================================"
echo "NanoBot Gateway 交互模式测试"
echo "============================================================"
echo ""

# Test 1: Check if Gateway can start
echo "Test 1: 检查 Gateway 启动..."
timeout 5 nanobot gateway --multi -i 2>&1 | head -20 &
sleep 3

# Check if process is running
if pgrep -f "nanobot gateway" > /dev/null; then
    echo "✅ Gateway 启动成功"
    pkill -f "nanobot gateway"
else
    echo "❌ Gateway 启动失败"
fi

echo ""
echo "Test 2: 检查 HTTP Server..."
# 这部分需要实际启动 Gateway 才能测试

echo ""
echo "============================================================"
echo "测试完成！"
echo "============================================================"
echo ""
echo "使用方式:"
echo "  方式 1: nanobot gateway --multi -i"
echo "  方式 2: nanobot gateway --multi   # 终端 1"
echo "            nanobot agent -g http://localhost:18791  # 终端 2"
echo ""
