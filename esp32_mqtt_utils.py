# esp32_mqtt_utils.py：工具类文件，封装MQTT自动接收功能
import paho.mqtt.client as mqtt
from threading import Thread
import json
from kivy.clock import Clock  # 确保UI更新线程安全

# 定义MQTT客户端类，封装所有通信相关功能
class Esp32MqttClient:
    def __init__(self, broker, port, username, password, data_callback):
        """
        初始化MQTT客户端
        :param broker: EMQX Broker地址
        :param port: EMQX端口（8883 for TLS）
        :param username: 认证用户名
        :param password: 认证密码
        :param data_callback: 数据接收回调函数（用于传递数据到主文件UI）
        """
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.data_callback = data_callback  # 回调函数，用于传递接收的数据
        self.mqtt_client = None
        self.mqtt_thread = None
        self.connected = False
        self.parsed_data_callback = None  # 解析后的数据回调
        self.latest_data = {}  # 存储最新传感器数据

    def set_parsed_data_callback(self, callback):
        """设置解析后的数据回调（供UI层注册，关键：用于自动更新UI）"""
        self.parsed_data_callback = callback

    def init_mqtt_client(self):
        """初始化MQTT客户端配置，绑定回调函数"""
        # 创建MQTT客户端实例
        self.mqtt_client = mqtt.Client()
        # 设置认证信息
        self.mqtt_client.username_pw_set(self.username, self.password)
        # 配置TLS加密（EMQX Serverless版本强制要求）
        self.mqtt_client.tls_set()
        # 绑定MQTT内置回调函数
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message

    def start_mqtt(self):
        """启动MQTT通信（独立线程，避免阻塞UI）"""
        self.init_mqtt_client()
        # 创建并启动MQTT线程
        self.mqtt_thread = Thread(target=self._mqtt_loop, daemon=True).start()

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT连接成功/失败回调（内部方法，不对外暴露）"""
        if rc == 0:
            self.connected = True
            self.data_callback("✅ MQTT连接成功，已开始自动接收数据")
            # 订阅需要自动接收的主题（关键：ESP32发送的消息必须对应该主题）
            client.subscribe("esp32/sensor")  # 传感器数据主题（核心订阅）
            client.subscribe("esp32/threshold_response")
        else:
            self.connected = False
            self.data_callback(f"❌ MQTT连接失败，无法自动接收数据（错误码：{rc}）")

    def _on_message(self, client, userdata, msg):
        """
        消息到达自动触发（核心：自动接收数据的入口）
        无需手动调用，MQTT客户端收到订阅主题的消息后，自动执行该方法
        """
        try:
            # 1. 解析原始消息
            topic = msg.topic
            payload = msg.payload.decode("utf-8")  # 二进制转字符串
            self.data_callback(f"📥 收到消息：[{topic}] {payload}")  # 转发原始消息到日志

            # 2. 只解析传感器主题的JSON数据（自动接收的核心数据）
            if topic == "esp32/sensor":
                # 解析为JSON字典（ESP32必须发送标准JSON，如：{"do":7.25, "ph":7.0, "temp":25.5}）
                parsed_data = json.loads(payload)
                self.latest_data = parsed_data  # 保存最新数据，供随时调用
                print(f"类型：{type(parsed_data)}")  # 打印数据类型（应为dict）
                print(f"完整数据：{parsed_data}")     # 打印完整字典
                print(f"溶解氧(do)：{parsed_data.get('do', '未获取到')}")  # 打印单个字段
                print(f"PH值(ph)：{parsed_data.get('ph', '未获取到')}")    # 打印单个字段
                print(f"温度(temp)：{parsed_data.get('temp', '未获取到')}")# 打印单个字段

                # 3. 自动转发解析后的数据到UI层（线程安全）
                if self.parsed_data_callback:
                    # Clock.schedule_once：确保UI更新在Kivy主线程执行，避免崩溃
                    Clock.schedule_once(lambda dt: self.parsed_data_callback(parsed_data))

        except json.JSONDecodeError:
            self.data_callback(f"❌ 数据格式错误：非标准JSON（{payload}）")
        except Exception as e:
            self.data_callback(f"❌ 自动接收数据失败：{str(e)}")

    def _mqtt_loop(self):
        """MQTT客户端循环（修复参数冲突+增加自动重连+超时）"""
        reconnect_interval = 5  # 重连间隔5秒
        max_reconnect_attempts = 10  # 最大重连次数
        reconnect_count = 0

        while reconnect_count < max_reconnect_attempts:
            try:
                # 修复核心问题：删除重复的keepalive参数，仅保留位置参数60
                self.mqtt_client.connect(self.broker, self.port, 60)
                self.connected = True
                self.data_callback("✅ MQTT连接成功，已开始自动接收数据")
                # 连接成功后持续监听
                self.mqtt_client.loop_forever()
                break  # 正常退出循环
            except Exception as e:
                reconnect_count += 1
                self.connected = False
                error_msg = f"❌ 连接失败（第{reconnect_count}/{max_reconnect_attempts}次重连）：{str(e)}"
                print(error_msg)
                self.data_callback(error_msg)
                # 达到最大次数则停止重连
                if reconnect_count >= max_reconnect_attempts:
                    self.data_callback("❌ 已达到最大重连次数，停止尝试")
                    break
                # 等待后重试
                import time
                time.sleep(reconnect_interval)
        # 重连失败后标记状态
        if reconnect_count >= max_reconnect_attempts:
            self.connected = False

    def publish_command(self, topic, command):
        """
        对外暴露：发布指令到ESP32
        :param topic: 发布主题（如esp32/control）
        :param command: 指令内容（如pause/resume）
        :return: 发送结果（布尔值）
        """
        if not self.connected:
            message = "❌ MQTT未连接，无法发送指令"
            print(message)
            self.data_callback(message)
            return False
        try:
            self.mqtt_client.publish(topic, command, qos=0)
            message = f"📤  已发送：{command}"
            print(message)
            self.data_callback(message)
            return True
        except Exception as e:
            message = f"❌ 发送失败：{str(e)}"
            print(message)
            self.data_callback(message)
            return False