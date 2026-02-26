# ui_utils.py：UI通用工具（组件、字体、页面切换）
from kivymd.uix.label import MDLabel
from kivy.uix.button import ButtonBehavior
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.clock import Clock

# 通用按钮组件
class NoBorderButton(ButtonBehavior, MDLabel):
    def __init__(self, **kwargs):
        self.button_type = kwargs.pop("button_type", "normal")
        super().__init__(**kwargs)
        self.font_name = "CustomChinese"
        self.halign = "center"
        self.valign = "middle"
        self.font_size = dp(16)
        
        if self.button_type == "switch":
            self.state_colors = {
                "关": {"bg": (0.8, 0.8, 0.8, 1), "text": (0, 0, 0, 1)},
                "开": {"bg": (0.8, 0.2, 0.2, 1), "text": (1, 1, 1, 1)}
            }
            self.current_state = "关"
        else:
            self.normal_colors = {"bg": (0.8, 0.8, 0.8, 1), "text": (0, 0, 0, 1)}
            self.pressed_colors = {"bg": (0.2, 0.5, 0.8, 1), "text": (1, 1, 1, 1)}
            self.is_pressed = False
        
        self.is_disabled = False
        self.update_button_colors()

    def update_button_colors(self):
        if self.is_disabled:
            self.md_bg_color = (0.9, 0.9, 0.9, 1)
            self.text_color = (0.5, 0.5, 0.5, 1)
            self.disabled = True
        else:
            if self.button_type == "switch":
                self.md_bg_color = self.state_colors[self.current_state]["bg"]
                self.text_color = self.state_colors[self.current_state]["text"]
            else:
                if self.is_pressed:
                    self.md_bg_color = self.pressed_colors["bg"]
                    self.text_color = self.pressed_colors["text"]
                else:
                    self.md_bg_color = self.normal_colors["bg"]
                    self.text_color = self.normal_colors["text"]
            self.disabled = False

    def reset_button_state(self):
        if self.button_type != "switch":
            self.is_pressed = False
            self.update_button_colors()

# 注册中文字体
def register_chinese_font():
    LabelBase.register(
        name="CustomChinese",
        fn_regular="Font_0.ttf"
    )

# 页面切换工具函数（优化回调清理）
def switch_page(app_instance, page_name):
    from app_ui_pages import create_home_page, create_me_page, create_history_page, unregister_history_callback, HISTORY_UPDATE_CALLBACKS
    # 清理当前页面的回调（如果是历史页面）
    if hasattr(app_instance, 'current_page') and app_instance.current_page:
        page_texts = [child.text for child in app_instance.current_page.children if isinstance(child, MDLabel)]
        if "设备历史数据" in page_texts:
            # 注销所有历史数据回调
            for cb in HISTORY_UPDATE_CALLBACKS[:]:
                unregister_history_callback(cb)
    
    app_instance.page_container.clear_widgets()
    if page_name == "home":
        app_instance.current_page = create_home_page(app_instance)
    elif page_name == "me":
        app_instance.current_page = create_me_page(app_instance)
    elif page_name == "history":
        # 每次切换到历史页面都重新创建，确保加载最新数据
        app_instance.current_page = create_history_page(app_instance)
    app_instance.page_container.add_widget(app_instance.current_page)