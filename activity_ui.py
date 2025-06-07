import os
import json
import asyncio
from datetime import datetime, timedelta, date
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

from activity_retriever import query_recent_activity, load_and_index_activity_data, get_all_activity_records, get_application_usage_summary

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# 确保templates目录存在
os.makedirs('templates', exist_ok=True)

# 存储聊天历史
chat_history = []

# --- 应用启动时加载一次数据 ---
def initial_load_data():
    print("应用启动：正在尝试加载和索引屏幕活动数据...")
    try:
        count = load_and_index_activity_data() # 这是同步函数
        print(f"应用启动：加载了 {count} 条新记录。")
    except Exception as e:
        print(f"应用启动：加载数据时出错: {e}")

# -----------------------------

@app.route('/')
def index():
    """主页"""
    return render_template('activity_chat.html')

@app.route('/api/query', methods=['POST'])
async def query_activity():
    """处理活动查询API请求"""
    data = request.json
    user_message = data.get('message', '')
    # time_range = int(data.get('time_range', 30))  # 不再需要从前端获取固定的time_range
    
    # 将用户消息添加到历史
    chat_history.append({"role": "user", "content": user_message})
    
    # 创建自定义提示词，现在将用户完整消息作为主要输入，让后端判断时间
    # 后端将根据 query_text (即 user_message) 来解析时间，或者使用默认回退机制
    custom_prompt_for_llm = f"""请根据屏幕活动记录回答用户的问题: {user_message}
如果问题无法直接从活动记录中回答，请基于你的知识进行回答，并说明这不是从我的屏幕活动中得出的结论。
如果用户的问题中包含类似"昨天"、"今天上午"、"上周"等时间描述，请确保你的回答严格基于该时间段的活动记录。
"""
    
    # 查询活动
    # result = await query_recent_activity(minutes_ago=time_range, custom_prompt=custom_prompt)
    # 修改调用，传递 user_message 给 query_text 参数，不再固定传递 minutes_ago
    # minutes_ago 可以作为后端无法解析时间时的回退选项，在 activity_retriever.py 中处理
    result = await query_recent_activity(query_text=user_message, custom_prompt=custom_prompt_for_llm)
    
    # 将助手回复添加到历史
    chat_history.append({"role": "assistant", "content": result})
    
    # 限制历史记录长度，避免占用过多内存
    if len(chat_history) > 100:
        chat_history.pop(0)
        chat_history.pop(0)
    
    return jsonify({
        'result': result,
        # 'time_range': time_range, # 不再需要在响应中返回固定的 time_range
        'query_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'history': chat_history
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    """获取聊天历史"""
    return jsonify(chat_history)

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    """清除聊天历史"""
    global chat_history
    chat_history = []
    return jsonify({"success": True})

@app.route('/api/activity_records', methods=['GET'])
def activity_records():
    """获取活动记录"""
    # 在获取记录前，尝试加载新数据 (移除这部分)
    # try:
    #     # print("API调用 /api/activity_records: 尝试加载新数据...")
    #     load_and_index_activity_data() 
    #     # print("API调用 /api/activity_records: 数据加载完成。")
    # except Exception as e:
    #     print(f"API调用 /api/activity_records: 加载数据时出错: {e}")
        
    limit = request.args.get('limit', 50, type=int)
    records = get_all_activity_records(limit)
    return jsonify(records)

@app.route('/api/activity_record/<record_id>', methods=['GET'])
def activity_record_detail(record_id):
    """获取单条活动记录详情"""
    records = get_all_activity_records(1000)  # 获取足够多的记录以找到指定ID
    for record in records:
        if record.get('id') == record_id:
            return jsonify(record)
    return jsonify({"error": "记录未找到"}), 404

@app.route('/api/usage_stats', methods=['GET'])
async def usage_stats():
    """获取应用使用时长统计数据"""
    # 在获取统计前，尝试加载新数据 (移除这部分)
    # try:
    #     # print("API调用 /api/usage_stats: 尝试加载新数据...")
    #     load_and_index_activity_data()
    #     # print("API调用 /api/usage_stats: 数据加载完成。")
    # except Exception as e:
    #     print(f"API调用 /api/usage_stats: 加载数据时出错: {e}")

    period = request.args.get('period', 'today') # today, yesterday, this_week, this_month
    # 如果需要支持自定义日期范围，可以添加 start_date 和 end_date 参数
    # custom_date_str = request.args.get('date') # 例如 'YYYY-MM-DD'

    now = datetime.now()
    start_time_dt = None
    end_time_dt = None

    if period == 'today':
        start_time_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time_dt = now
    elif period == 'yesterday':
        yesterday_dt = now - timedelta(days=1)
        start_time_dt = yesterday_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time_dt = yesterday_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == 'this_week':
        start_of_week = now - timedelta(days=now.weekday()) # 周一为0, 周日为6
        start_time_dt = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time_dt = now
    elif period == 'this_month':
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_time_dt = start_of_month
        end_time_dt = now
    # elif custom_date_str: # 支持选择特定某一天
    #     try:
    #         target_date = datetime.strptime(custom_date_str, '%Y-%m-%d').date()
    #         start_time_dt = datetime.combine(target_date, datetime.min.time())
    #         end_time_dt = datetime.combine(target_date, datetime.max.time())
    #     except ValueError:
    #         return jsonify({"error": "无效的日期格式，请使用YYYY-MM-DD"}), 400
    else:
        # 默认或未知周期，返回今日数据
        start_time_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time_dt = now
        period = 'today' # 确保period有一个有效值

    summary_data = await get_application_usage_summary(start_time_dt, end_time_dt)

    if summary_data.get("error"):
        return jsonify({"error": summary_data.get("error"), "period_processed": period}), 500

    # 格式化输出，将timedelta转换为总分钟数或小时分钟字符串
    formatted_usage = []
    total_duration_all_apps = timedelta()

    sorted_usage = sorted(summary_data["usage"].items(), key=lambda item: item[1], reverse=True)

    for app, duration_td in sorted_usage:
        total_seconds = duration_td.total_seconds()
        total_duration_all_apps += duration_td
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = ""
        if hours > 0:
            duration_str += f"{int(hours)}小时"
        if minutes > 0:
            duration_str += f" {int(minutes)}分钟"
        if not duration_str: # 如果不足一分钟，显示秒
             duration_str = f"{int(seconds)}秒"
        
        formatted_usage.append({
            "app_name": app if app and app != "Unknown" else "其他/未知",
            "duration_seconds": total_seconds,
            "duration_str": duration_str.strip()
        })
    
    total_all_seconds = total_duration_all_apps.total_seconds()
    total_hours, total_remainder = divmod(total_all_seconds, 3600)
    total_minutes, _ = divmod(total_remainder, 60)
    total_duration_str = f"{int(total_hours)}小时 {int(total_minutes)}分钟"

    return jsonify({
        "period_processed": period,
        "start_time": start_time_dt.isoformat(),
        "end_time": end_time_dt.isoformat(),
        "total_usage_str": total_duration_str,
        "total_usage_seconds": total_all_seconds,
        "app_specific_usage": formatted_usage,
        # "raw_events_sample": summary_data["raw_events"][:5] # 可选：用于调试
    })

if __name__ == '__main__':
    # 启动Flask应用前先加载一次数据
    # initial_load_data() # <--- 暂时注释掉这一行
    # 创建HTML模板
    with open('templates/activity_chat.html', 'w', encoding='utf-8') as f:
        f.write("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>屏幕活动助手</title>
    <style>
        :root {
            --primary-color: #10a37f;
            --bg-color: #f7f7f8;
            --chat-bg: #ffffff;
            --user-bubble: #10a37f;
            --user-text: white;
            --bot-bubble: #f7f7f8;
            --bot-text: #343541;
            --border-color: #e5e5e5;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
            line-height: 1.6;
            color: #343541;
            background-color: var(--bg-color);
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            text-align: center;
            padding: 15px;
            background-color: white;
            box-shadow: 0 1px 5px rgba(0,0,0,0.1);
            z-index: 10;
        }
        
        .header h1 {
            font-size: 24px;
            color: var(--primary-color);
        }
        
        .main-container {
            display: flex;
            flex: 1;
            max-width: 1600px; /* Increased max-width for three columns */
            margin: 0 auto;
            width: 100%;
            height: calc(100vh - 70px); /* Adjusted height */
            padding: 10px; /* Add padding around main container */
        }
        
        .left-sidebar { /* New Left Sidebar for Stats */
            flex: 1;
            background: var(--chat-bg);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            padding: 10px;
            margin-right: 10px; /* Space between left sidebar and chat */
        }
        
        .chat-container {
            flex: 2; /* Chat area takes more space */
            display: flex;
            flex-direction: column;
            background: var(--chat-bg);
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .activity-sidebar { /* This is now the Right Sidebar */
            flex: 1;
            background: var(--chat-bg);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            padding: 10px; /* Add some padding */
            margin-left: 10px; /* Space between chat and right sidebar */
        }
        
        .sidebar-header {
            padding: 10px 5px;
            background-color: #f0f0f0;
            border-bottom: 1px solid var(--border-color);
            font-weight: bold;
            text-align: center;
            border-top-left-radius: 5px; /* Rounded corners for header */
            border-top-right-radius: 5px;
        }

        .usage-stats-container { /* New container for all stats elements */
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        .time-range-selector {
            display: flex;
            justify-content: space-around;
            padding: 10px 0;
            border-bottom: 1px solid var(--border-color);
        }

        .time-range-selector button {
            padding: 8px 12px;
            border: 1px solid var(--border-color);
            background-color: white;
            cursor: pointer;
            border-radius: 5px;
            transition: background-color 0.2s, color 0.2s;
        }

        .time-range-selector button.active {
            background-color: var(--primary-color);
            color: white;
            border-color: var(--primary-color);
        }
        
        .total-usage-display {
            padding: 15px 5px;
            text-align: center;
            font-size: 16px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .total-usage-display strong {
            font-size: 20px;
            color: var(--primary-color);
            display: block; /* Make it block to show on new line */
            margin-top: 5px;
        }

        .app-usage-list { /* Renamed from activity-list */
            flex: 1;
            overflow-y: auto;
            padding: 10px 0px; /* Adjusted padding */
        }
        
        .app-usage-item { /* Renamed from activity-item */
            padding: 10px 5px;
            border-bottom: 1px solid #eee; /* Lighter border */
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .app-usage-item:last-child {
            border-bottom: none;
        }
        
        .app-info {
            flex-grow: 1;
        }

        .app-info .app-name {
            font-size: 14px;
            font-weight: 500;
            color: #333;
        }

        .app-info .app-duration-str {
            font-size: 12px;
            color: #666;
        }
        
        .app-duration-bar-container {
            width: 100px; /* Adjust as needed */
            height: 10px;
            background-color: #e0e0e0;
            border-radius: 5px;
            overflow: hidden; /* To make inner bar rounded */
            margin-left: 10px;
        }

        .app-duration-bar {
            height: 100%;
            background-color: var(--primary-color);
            width: 0%; /* Will be set by JS */
            border-radius: 5px;
            transition: width 0.5s ease-in-out;
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }
        
        .message {
            display: flex;
            margin-bottom: 20px;
        }
        
        .message.user {
            justify-content: flex-end;
        }
        
        .message-content {
            padding: 12px 16px;
            border-radius: 20px;
            max-width: 70%;
            word-wrap: break-word;
        }
        
        .user .message-content {
            background-color: var(--user-bubble);
            color: var(--user-text);
            border-top-right-radius: 4px;
        }
        
        .assistant .message-content {
            background-color: var(--bot-bubble);
            color: var(--bot-text);
            border-top-left-radius: 4px;
            border: 1px solid var(--border-color);
        }
        
        .input-area {
            display: flex;
            padding: 15px;
            background-color: white;
            border-top: 1px solid var(--border-color);
        }
        
        .message-input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid var(--border-color);
            border-radius: 20px;
            font-size: 16px;
            outline: none;
            resize: none;
            overflow-y: auto;
            max-height: 120px;
        }
        
        .message-input:focus {
            border-color: var(--primary-color);
        }
        
        .send-button {
            background-color: var(--primary-color);
            color: white;
            border: none;
            border-radius: 20px;
            padding: 0 20px;
            margin-left: 10px;
            cursor: pointer;
            font-weight: bold;
            transition: background-color 0.2s;
        }
        
        .send-button:hover {
            background-color: #0d8c6f;
        }
        
        .send-button:disabled {
            background-color: #e5e5e5;
            cursor: not-allowed;
        }
        
        .loading {
            display: flex;
            justify-content: center;
            margin: 10px 0;
        }
        
        .loading-dots {
            display: flex;
        }
        
        .dot {
            width: 8px;
            height: 8px;
            background-color: #10a37f;
            border-radius: 50%;
            margin: 0 3px;
            animation: pulse 1.5s infinite ease-in-out;
        }
        
        .dot:nth-child(2) {
            animation-delay: 0.2s;
        }
        
        .dot:nth-child(3) {
            animation-delay: 0.4s;
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(0.8); opacity: 0.6; }
            50% { transform: scale(1.2); opacity: 1; }
        }
        
        .clear-button {
            background-color: transparent;
            color: #888;
            border: 1px solid #ddd;
            border-radius: 20px;
            padding: 0 15px;
            margin-left: 10px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .clear-button:hover {
            background-color: #f0f0f0;
        }
        
        .actions {
            display: flex;
            justify-content: flex-end;
            padding: 5px 20px;
        }
        
        /* Modal */
        .modal {
            display: none;
            position: fixed;
            z-index: 100;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        
        .modal-content {
            background-color: white;
            margin: 10% auto;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            width: 80%;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .modal-header h2 {
            margin: 0;
            font-size: 20px;
            color: var(--primary-color);
        }
        
        .modal-close {
            font-size: 24px;
            cursor: pointer;
            color: #999;
            background: none;
            border: none;
        }
        
        .modal-close:hover {
            color: #333;
        }
        
        .modal-body {
            white-space: pre-wrap;
            font-family: monospace;
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            margin-top: 10px;
        }
        
        .modal-meta {
            margin-bottom: 15px;
            color: #666;
            font-size: 14px;
        }
        
        /* 适应移动设备 */
        @media (max-width: 768px) {
            .main-container {
                flex-direction: column;
                height: auto;
            }
            
            .chat-container {
                height: 70vh;
                margin-right: 0;
                margin-bottom: 10px;
            }
            
            .activity-sidebar {
                height: 30vh;
            }
            
            .message-content {
                max-width: 85%;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>智能屏幕活动助手</h1>
    </div>
    
    <div class="main-container">
        <div class="left-sidebar">
            <div class="usage-stats-container" id="usage-stats-left-sidebar">
                <div class="sidebar-header">
                    屏幕使用时长统计
                </div>
                <div class="time-range-selector" id="time-range-selector-left">
                    <button data-period="today" class="active">今日</button>
                    <button data-period="yesterday">昨日</button>
                    <button data-period="this_week">本周</button>
                    <button data-period="this_month">本月</button>
                </div>
                <div class="total-usage-display" id="total-usage-display-left">
                    正在加载总时长...
                </div>
                <div class="app-usage-list" id="app-usage-list-left">
                     <div class="loading" style="display:none;" id="usage-loading-indicator-left">
                        <div class="loading-dots">
                            <div class="dot"></div>
                            <div class="dot"></div>
                            <div class="dot"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="chat-container">
            <div class="chat-messages" id="chat-messages">
                <div class="message assistant">
                    <div class="message-content">
                        你好！我是您的屏幕活动助手。您可以问我关于您的屏幕活动的任何问题，例如"我刚才在浏览什么网站？"或"我最近都使用了哪些软件？"
                    </div>
                </div>
            </div>
            
            <div class="actions">
                <button class="clear-button" id="clear-button">清除聊天记录</button>
            </div>
            
            <div class="input-area">
                <textarea class="message-input" id="message-input" placeholder="输入您的问题..." rows="1"></textarea>
                <button class="send-button" id="send-button">发送</button>
            </div>
        </div>
        
        <div class="activity-sidebar">
            <div class="sidebar-header" id="right-sidebar-header">
                最近屏幕活动记录
            </div>
            <div class="activity-list" id="activity-list-right">
                <div class="loading" id="activity-loading-indicator-right">
                    <div class="loading-dots">
                        <div class="dot"></div>
                        <div class="dot"></div>
                        <div class="dot"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- 活动详情模态框 -->
    <div id="activity-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modal-title">活动详情</h2>
                <button class="modal-close">&times;</button>
            </div>
            <div class="modal-meta" id="modal-meta"></div>
            <div class="modal-body" id="modal-body"></div>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const messagesContainer = document.getElementById('chat-messages');
            const messageInput = document.getElementById('message-input');
            const sendButton = document.getElementById('send-button');
            const clearButton = document.getElementById('clear-button');
            const activityList = document.getElementById('activity-list');
            const modal = document.getElementById('activity-modal');
            const modalTitle = document.getElementById('modal-title');
            const modalMeta = document.getElementById('modal-meta');
            const modalBody = document.getElementById('modal-body');
            const modalClose = document.querySelector('.modal-close');
            
            // Elements for LEFT usage stats sidebar
            const timeRangeSelectorLeft = document.getElementById('time-range-selector-left');
            const totalUsageDisplayLeft = document.getElementById('total-usage-display-left');
            const appUsageListLeft = document.getElementById('app-usage-list-left');
            const usageLoadingIndicatorLeft = document.getElementById('usage-loading-indicator-left');

            // Elements for RIGHT activity list sidebar
            const activityListRight = document.getElementById('activity-list-right');
            const activityLoadingIndicatorRight = document.getElementById('activity-loading-indicator-right');

            let currentPeriod = 'today';

            // Load usage stats for LEFT sidebar
            loadUsageStats(currentPeriod);

            // Load activity records for RIGHT sidebar
            loadActivityRecords();
            
            // Event listener for LEFT time range selector buttons
            if (timeRangeSelectorLeft) {
                timeRangeSelectorLeft.addEventListener('click', function(e) {
                    if (e.target.tagName === 'BUTTON') {
                        const period = e.target.dataset.period;
                        if (period && period !== currentPeriod) {
                            currentPeriod = period;
                            timeRangeSelectorLeft.querySelectorAll('button').forEach(btn => btn.classList.remove('active'));
                            e.target.classList.add('active');
                            loadUsageStats(currentPeriod);
                        }
                    }
                });
            }

            // 自动调整文本区域高度
            messageInput.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = (this.scrollHeight) + 'px';
                // 限制最大高度
                if (this.scrollHeight > 120) {
                    this.style.height = '120px';
                    this.style.overflowY = 'auto';
                } else {
                    this.style.overflowY = 'hidden';
                }
            });
            
            // 按Enter发送消息（Shift+Enter换行）
            messageInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
            
            // 发送按钮点击事件
            sendButton.addEventListener('click', sendMessage);
            
            // 清除聊天记录按钮
            clearButton.addEventListener('click', clearChatHistory);
            
            // 关闭模态框
            modalClose.addEventListener('click', function() {
                modal.style.display = 'none';
            });
            
            // 点击模态框外部关闭
            window.addEventListener('click', function(event) {
                if (event.target === modal) {
                    modal.style.display = 'none';
                }
            });
            
            // 加载聊天历史
            loadChatHistory();
            
            // 定期刷新活动记录（每30秒）
            setInterval(loadActivityRecords, 30000); // For RIGHT sidebar
            
            // 定期刷新左侧使用时长统计 (例如每60秒)
            setInterval(function() {
                loadUsageStats(currentPeriod); // 使用当前选定的时间段
            }, 60000); // 60000 毫秒 = 60 秒

            // Function to load and display usage statistics for LEFT sidebar
            async function loadUsageStats(period) {
                if (usageLoadingIndicatorLeft) usageLoadingIndicatorLeft.style.display = 'flex';
                if (appUsageListLeft) appUsageListLeft.innerHTML = '';
                if (totalUsageDisplayLeft) totalUsageDisplayLeft.textContent = '正在计算总时长...';

                try {
                    const response = await fetch(`/api/usage_stats?period=${period}`);
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                    }
                    const stats = await response.json();
                    
                    if (totalUsageDisplayLeft) totalUsageDisplayLeft.innerHTML = `总计使用: <strong>${stats.total_usage_str}</strong>`;
                    
                    if (stats.app_specific_usage.length === 0) {
                        if (appUsageListLeft) appUsageListLeft.innerHTML = '<p style="padding: 15px; color: #666; text-align:center;">该时段暂无应用使用记录</p>';
                    } else {
                        const maxDuration = Math.max(...stats.app_specific_usage.map(app => app.duration_seconds), 0);

                        stats.app_specific_usage.forEach(app => {
                            const item = document.createElement('div');
                            item.className = 'app-usage-item';
                            
                            const percentage = (maxDuration > 0) ? (app.duration_seconds / maxDuration) * 100 : 0;

                            item.innerHTML = `
                                <div class="app-info">
                                    <div class="app-name">${app.app_name}</div>
                                    <div class="app-duration-str">${app.duration_str}</div>
                                </div>
                                <div class="app-duration-bar-container">
                                    <div class="app-duration-bar" style="width: ${percentage}%;"></div>
                                </div>
                            `;
                            if (appUsageListLeft) appUsageListLeft.appendChild(item);
                        });
                    }
                } catch (error) {
                    console.error(`加载使用统计(${period})失败:`, error);
                    if (totalUsageDisplayLeft) totalUsageDisplayLeft.textContent = '获取时长失败';
                    if (appUsageListLeft) appUsageListLeft.innerHTML = `<p style="padding: 15px; color: red; text-align:center;">加载统计数据失败: ${error.message}</p>`;
                } finally {
                    if (usageLoadingIndicatorLeft) usageLoadingIndicatorLeft.style.display = 'none';
                }
            }

            // Function to load and display activity records for RIGHT sidebar
            async function loadActivityRecords() {
                if(activityLoadingIndicatorRight) activityLoadingIndicatorRight.style.display = 'flex';
                if(activityListRight) activityListRight.innerHTML = ''; // Clear before loading

                try {
                    const response = await fetch('/api/activity_records'); 
                    const records = await response.json();
                    
                    if(activityListRight) {
                        if (records.length === 0) {
                            activityListRight.innerHTML = '<p style="padding: 15px; color: #666; text-align:center;">暂无活动记录</p>';
                            return;
                        }
                        
                        records.forEach(record => {
                            const item = document.createElement('div');
                            item.className = 'activity-item';
                            item.dataset.id = record.id;
                            
                            const timestamp = new Date(record.timestamp);
                            const timeStr = timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                            
                            // 优先显示URL作为预览，否则显示OCR文本
                            const textPreview = record.url ? 
                                record.url : 
                                (record.ocr_text.length > 60 ? 
                                    record.ocr_text.substring(0, 60) + '...' : 
                                    record.ocr_text);
                            
                            let titleToShow;
                            if (record.app_name && record.app_name !== "Unknown") {
                                if (record.page_title) {
                                    titleToShow = `${record.app_name} - ${record.page_title}`;
                                } else if (record.window_title && record.app_name !== record.window_title && !record.window_title.includes(record.app_name)) {
                                    titleToShow = `${record.app_name} - ${record.window_title}`;
                                } else {
                                    titleToShow = record.app_name;
                                }
                            } else if (record.window_title) { // app_name is Unknown or missing, use window_title
                                titleToShow = record.window_title;
                            } else { // Fallback if everything is missing
                                titleToShow = "未知活动";
                            }

                            item.innerHTML = `
                                <h3>${titleToShow}</h3>
                                <p>${textPreview}</p>
                                <div class="timestamp">${timeStr}</div>
                            `;
                            
                            item.addEventListener('click', function() {
                                showActivityDetail(record);
                            });
                            
                            activityListRight.appendChild(item);
                        });
                    }
                } catch (error) {
                    console.error('加载活动记录(右侧边栏)失败:', error);
                    if(activityListRight) activityListRight.innerHTML = '<p style="padding: 15px; color: red; text-align:center;">加载活动记录失败</p>';
                } finally {
                    if(activityLoadingIndicatorRight) activityLoadingIndicatorRight.style.display = 'none';
                }
            }
            
            // 显示活动详情 (旧函数，用于模态框)
            function showActivityDetail(record) {
                let detailTitle;
                if (record.app_name && record.app_name !== "Unknown") {
                    if (record.page_title) {
                        detailTitle = `${record.app_name} - ${record.page_title}`;
                    } else if (record.window_title && record.app_name !== record.window_title && !record.window_title.includes(record.app_name)) {
                        detailTitle = `${record.app_name} - ${record.window_title}`;
                    } else {
                        detailTitle = record.app_name;
                    }
                } else if (record.window_title) {
                    detailTitle = record.window_title;
                } else {
                    detailTitle = "活动详情";
                }
                modalTitle.textContent = detailTitle;
                
                const timestamp = new Date(record.timestamp);
                const dateTimeStr = timestamp.toLocaleString();
                
                // 在元信息中添加可点击的URL链接
                modalMeta.innerHTML = `
                    <strong>时间:</strong> ${dateTimeStr}<br>
                    <strong>应用:</strong> ${record.app_name || '未知'}<br>
                    ${record.url ? `<strong>URL:</strong> <a href="${record.url}" target="_blank">${record.url}</a><br>` : ''}
                    <strong>窗口标题:</strong> ${record.window_title || '无'}<br>
                    ${record.page_title ? `<strong>页面标题:</strong> ${record.page_title}<br>` : ''}
                `;
                
                modalBody.textContent = record.ocr_text;
                modal.style.display = 'block';
            }
            
            // 发送消息函数
            async function sendMessage() {
                const message = messageInput.value.trim();
                if (!message) return;
                
                // 清空输入框并重置高度
                messageInput.value = '';
                messageInput.style.height = 'auto';
                
                // 添加用户消息到聊天界面
                addMessage('user', message);
                
                // 显示加载动画
                const loadingElement = document.createElement('div');
                loadingElement.className = 'loading';
                loadingElement.innerHTML = '<div class="loading-dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>';
                messagesContainer.appendChild(loadingElement);
                scrollToBottom();
                
                // 禁用发送按钮
                sendButton.disabled = true;
                
                try {
                    // 发送请求到服务器
                    const response = await fetch('/api/query', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            message: message
                        })
                    });
                    
                    const data = await response.json();
                    
                    // 移除加载动画
                    messagesContainer.removeChild(loadingElement);
                    
                    // 添加助手回复
                    addMessage('assistant', data.result);
                    
                } catch (error) {
                    // 移除加载动画
                    if (loadingElement.parentNode) {
                        messagesContainer.removeChild(loadingElement);
                    }
                    
                    // 显示错误消息
                    addMessage('assistant', `抱歉，发生了错误: ${error.message}`);
                    
                } finally {
                    // 启用发送按钮
                    sendButton.disabled = false;
                }
            }
            
            // 添加消息到聊天界面
            function addMessage(role, content) {
                const messageElement = document.createElement('div');
                messageElement.className = `message ${role}`;
                
                const contentElement = document.createElement('div');
                contentElement.className = 'message-content';
                contentElement.textContent = content;
                
                messageElement.appendChild(contentElement);
                messagesContainer.appendChild(messageElement);
                
                scrollToBottom();
            }
            
            // 滚动到底部
            function scrollToBottom() {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
            
            // 加载聊天历史
            async function loadChatHistory() {
                try {
                    const response = await fetch('/api/history');
                    const history = await response.json();
                    
                    // 清空现有消息（除了欢迎消息）
                    while (messagesContainer.childNodes.length > 1) {
                        messagesContainer.removeChild(messagesContainer.lastChild);
                    }
                    
                    // 添加历史消息
                    for (const msg of history) {
                        addMessage(msg.role, msg.content);
                    }
                    
                } catch (error) {
                    console.error('加载聊天历史失败:', error);
                }
            }
            
            // 清除聊天历史
            async function clearChatHistory() {
                try {
                    await fetch('/api/clear_history', { method: 'POST' });
                    
                    // 清空聊天界面，只保留欢迎消息
                    while (messagesContainer.childNodes.length > 1) {
                        messagesContainer.removeChild(messagesContainer.lastChild);
                    }
                    
                } catch (error) {
                    console.error('清除聊天历史失败:', error);
                }
            }
        });
    </script>
</body>
</html>""")
    
    app.run(host='0.0.0.0', port=5001, debug=True) 