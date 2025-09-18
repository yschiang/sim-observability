#!/bin/bash

echo "🔥🔥🔥 重度 CPU Spike 模擬 (30-60秒持續時間)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 請在 Grafana 觀察: http://localhost:3000"
echo "   📊 B - CPU Usage (FastAPI) - 預期 100%+ 持續 30-60秒"
echo "   📊 B - Memory Usage - 預期從 25% 上升至 35%+"
echo "   📊 B - Requests/s 和 B - Requests/minute - 多重請求"
echo ""

# Check service health
curl -s http://localhost:8080/health > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ Service B 未運行，請執行: docker compose --profile python up -d"
    exit 1
fi

echo "✅ Service B 運行正常"
echo ""

echo "⚡ 當前基準狀態:"
echo "CPU: $(curl -s http://localhost:8081/metrics | grep '^b_cpu_usage_percent' | awk '{print $2}')%"
echo "Memory: $(docker stats --no-stream sim-observability-full-bundle-b-1 --format '{{.MemPerc}}')"
echo ""

echo "🚀 階段 1: 預熱 - 正常請求 (10秒)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for i in {1..10}; do
    curl -s "http://localhost:8080/process?device_id=warmup-$i&ms=50" > /dev/null &
    echo "  預熱請求 $i/10 已發送"
    sleep 1
done
wait
echo ""

echo "🔥 階段 2: 開始重度 CPU Spike (60秒持續)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 啟動多個並行的高強度批次處理..."

# 啟動第一個大型批次處理 (最重)
echo "🔥 批次 1: 8000 筆記錄，強度 3.0 (預期 30-40秒)"
curl -s -X POST "http://localhost:8080/batch_process?size=8000&intensity=3.0" > /tmp/batch1_heavy.json &
BATCH1_PID=$!

# 等待 5 秒讓第一個批次開始
sleep 5

# 啟動第二個批次處理
echo "🔥 批次 2: 6000 筆記錄，強度 2.5 (預期 20-30秒)"
curl -s -X POST "http://localhost:8080/batch_process?size=6000&intensity=2.5" > /tmp/batch2_heavy.json &
BATCH2_PID=$!

# 等待 8 秒
sleep 8

# 啟動第三個批次處理
echo "🔥 批次 3: 5000 筆記錄，強度 2.0 (預期 15-25秒)"
curl -s -X POST "http://localhost:8080/batch_process?size=5000&intensity=2.0" > /tmp/batch3_heavy.json &
BATCH3_PID=$!

# 在批次處理期間持續發送正常請求
echo ""
echo "📈 同時發送正常請求以增加 Requests/s 和 Requests/minute..."

# 背景持續發送請求
(
    for i in {1..60}; do
        for j in {1..3}; do
            curl -s "http://localhost:8080/process?device_id=load-$i-$j&ms=200" > /dev/null &
        done
        sleep 1
    done
) &
REQUEST_PID=$!

# 監控資源使用
echo ""
echo "📊 即時監控 (60秒):"
for second in {1..60}; do
    CPU=$(curl -s http://localhost:8081/metrics | grep '^b_cpu_usage_percent' | awk '{print $2}' 2>/dev/null || echo "0")
    MEM=$(docker stats --no-stream sim-observability-full-bundle-b-1 --format '{{.MemPerc}}' 2>/dev/null || echo "0%")
    BATCH_STATUS=$(curl -s http://localhost:8081/metrics | grep '^b_batch_processing' | awk '{print $2}' 2>/dev/null || echo "0")
    
    if [ "$BATCH_STATUS" = "1.0" ]; then
        STATUS="🔥 PROCESSING"
    else
        STATUS="⏸  IDLE"
    fi
    
    printf "[%2ds] CPU: %6.1f%% | Memory: %7s | Status: %s\n" $second $CPU $MEM "$STATUS"
    sleep 1
done

# 停止背景請求
kill $REQUEST_PID 2>/dev/null

echo ""
echo "⏳ 等待所有批次處理完成..."

# 等待所有批次完成
wait $BATCH1_PID 2>/dev/null
wait $BATCH2_PID 2>/dev/null  
wait $BATCH3_PID 2>/dev/null

echo ""
echo "📋 批次處理結果:"
if [ -f /tmp/batch1_heavy.json ]; then
    echo "  🔥 批次 1: $(cat /tmp/batch1_heavy.json | jq -r '.status + " - " + (.processing_time_ms/1000 | tostring) + "秒"' 2>/dev/null || echo "完成")"
fi

if [ -f /tmp/batch2_heavy.json ]; then
    echo "  🔥 批次 2: $(cat /tmp/batch2_heavy.json | jq -r '.status + " - " + (.processing_time_ms/1000 | tostring) + "秒"' 2>/dev/null || echo "完成")"
fi

if [ -f /tmp/batch3_heavy.json ]; then
    echo "  🔥 批次 3: $(cat /tmp/batch3_heavy.json | jq -r '.status + " - " + (.processing_time_ms/1000 | tostring) + "秒"' 2>/dev/null || echo "完成")"
fi

echo ""
echo "🔄 階段 3: 恢復期監控 (15秒)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for i in {1..15}; do
    CPU=$(curl -s http://localhost:8081/metrics | grep '^b_cpu_usage_percent' | awk '{print $2}' 2>/dev/null || echo "0")
    MEM=$(docker stats --no-stream sim-observability-full-bundle-b-1 --format '{{.MemPerc}}' 2>/dev/null || echo "0%")
    printf "  [恢復 %2ds] CPU: %6.1f%% | Memory: %7s\n" $i $CPU $MEM
    
    # 發送少量正常請求維持活動
    curl -s "http://localhost:8080/process?device_id=recovery-$i&ms=50" > /dev/null &
    sleep 1
done

echo ""
echo "✅ 重度 CPU Spike 模擬完成！"
echo ""
echo "📊 在 Grafana 中應該觀察到:"
echo "   🔥 CPU: 持續 30-60秒 的 100%+ 使用率"
echo "   📈 Memory: 從基準 25% 上升至峰值 35%+"
echo "   📊 Requests/s: 持續的請求流量 (3-5 req/s)"
echo "   📊 Requests/minute: 對應的分鐘級請求數 (180-300 req/min)"
echo "   💜 批次處理指示器: 顯示處理活動狀態"
echo ""
echo "🔗 Grafana 儀表板: http://localhost:3000"

# 清理臨時文件
rm -f /tmp/batch*_heavy.json

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"