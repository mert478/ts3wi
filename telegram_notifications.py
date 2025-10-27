import requests
import logging
from datetime import datetime
from typing import Dict, Optional
import json

class TelegramNotifier:
    """Telegram Bildirim Sınıfı - Sadece önemli bilgileri gönderir"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger(__name__)
        
        # Bildirim ayarları
        self.send_startup_notifications = True
        self.send_trade_notifications = True
        self.send_risk_notifications = True
        self.send_error_notifications = True
        self.send_daily_summary = True
        
        # Test bağlantısı
        self.test_connection()
    
    def test_connection(self):
        """Telegram bağlantısını test et"""
        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=10)
            if response.status_code == 200:
                bot_info = response.json()
                if bot_info['ok']:
                    self.logger.info(f"Telegram bağlantısı başarılı: @{bot_info['result']['username']}")
                    self.send_message("🤖 MegaTrend Bot Telegram bağlantısı başarılı!")
                    return True
            self.logger.error("Telegram bağlantısı başarısız")
            return False
        except Exception as e:
            self.logger.error(f"Telegram test hatası: {e}")
            return False
    
    def send_message(self, message: str, parse_mode: str = "HTML", disable_notification: bool = False):
        """Telegram mesajı gönder"""
        try:
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_notification': disable_notification
            }
            
            response = requests.post(f"{self.api_url}/sendMessage", data=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result['ok']:
                    return True
                else:
                    self.logger.error(f"Telegram mesaj hatası: {result}")
            else:
                self.logger.error(f"Telegram HTTP hatası: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Telegram mesaj gönderme hatası: {e}")
        
        return False
    
    def format_price(self, price: float) -> str:
        """Fiyatı güzel formatta göster"""
        return f"{price:.5f}"
    
    def format_percentage(self, percentage: float) -> str:
        """Yüzdeyi güzel formatta göster"""
        return f"{percentage:+.2f}%"
    
    def send_startup_notification(self, account_info: Dict):
        """Bot başlangıç bildirimi"""
        if not self.send_startup_notifications:
            return
        
        message = f"""🚀 <b>MegaTrend Bot Başlatıldı</b>

📊 <b>Hesap Bilgileri:</b>
• Hesap: {account_info.get('login', 'N/A')}
• Bakiye: ${account_info.get('balance', 0):,.2f}
• Özkaynak: ${account_info.get('equity', 0):,.2f}
• Marjin Seviyesi: {account_info.get('margin_level', 0):.1f}%

⚙️ <b>Bot Ayarları:</b>
• Sembol: XAUUSD
• Timeframe: M5
• Lot Size: 0.01
• Max Pozisyon: 3

🛡️ <b>Risk Yönetimi:</b>
• Max Drawdown: 20%
• Günlük Limit: 5%
• Market Filtreleri: Aktif

<i>Bot aktif olarak çalışmaya başladı!</i>"""
        
        self.send_message(message)
    
    def send_trade_notification(self, signal_data: Dict, order_type: str, entry_price: float, 
                              stop_loss: float, take_profit: float, lot_size: float):
        """İşlem bildirimi"""
        if not self.send_trade_notifications:
            return
        
        # Emoji seçimi
        emoji = "🟢" if order_type == "BUY" else "🔴"
        direction = "ALIM" if order_type == "BUY" else "SATIM"
        
        # Risk/Reward hesaplama
        if order_type == "BUY":
            risk = entry_price - stop_loss
            reward = take_profit - entry_price
        else:
            risk = stop_loss - entry_price
            reward = entry_price - take_profit
        
        rr_ratio = reward / risk if risk > 0 else 0
        
        message = f"""{emoji} <b>{direction} EMRİ VERİLDİ</b>

📈 <b>İşlem Detayları:</b>
• Sinyal: {signal_data.get('signal', 'N/A')}
• Güç: {signal_data.get('strength', 0)}/10
• Giriş: {self.format_price(entry_price)}
• Stop Loss: {self.format_price(stop_loss)}
• Take Profit: {self.format_price(take_profit)}
• Lot: {lot_size}

📊 <b>Teknik Analiz:</b>
• RSI: {signal_data.get('rsi', 0):.1f}
• MACD: {'Pozitif' if signal_data.get('macd_signal') else 'Negatif'}
• BB: {signal_data.get('bb_position', 'N/A').title()}

💰 <b>Risk/Reward:</b>
• Risk: {self.format_price(risk)}
• Reward: {self.format_price(reward)}
• R/R Oranı: 1:{rr_ratio:.1f}

<i>Zaman: {datetime.now().strftime('%H:%M:%S')}</i>"""
        
        self.send_message(message)
    
    def send_position_closed_notification(self, position_info: Dict, profit_loss: float, reason: str = ""):
        """Pozisyon kapatma bildirimi"""
        if not self.send_trade_notifications:
            return
        
        # Kar/zarar durumuna göre emoji
        emoji = "✅" if profit_loss > 0 else "❌" if profit_loss < 0 else "➖"
        status = "KAR" if profit_loss > 0 else "ZARAR" if profit_loss < 0 else "BAŞABAŞ"
        
        message = f"""{emoji} <b>POZİSYON KAPATILDI</b>

📊 <b>Sonuç:</b>
• Durum: {status}
• P&L: ${profit_loss:+.2f}
• Ticket: {position_info.get('ticket', 'N/A')}
• Lot: {position_info.get('volume', 0)}

{f"• Sebep: {reason}" if reason else ""}

<i>Zaman: {datetime.now().strftime('%H:%M:%S')}</i>"""
        
        self.send_message(message)
    
    def send_risk_notification(self, risk_type: str, current_value: float, limit_value: float, account_info: Dict):
        """Risk uyarı bildirimi"""
        if not self.send_risk_notifications:
            return
        
        if risk_type == "drawdown":
            message = f"""⚠️ <b>DRAWDOWN UYARISI!</b>

🔴 <b>Risk Durumu:</b>
• Mevcut Drawdown: {self.format_percentage(current_value)}
• Limit: {self.format_percentage(limit_value)}
• Bakiye: ${account_info.get('balance', 0):,.2f}
• Özkaynak: ${account_info.get('equity', 0):,.2f}

🛑 <b>İşlem durduruldu!</b>
Risk yönetimi devreye girdi."""
            
        elif risk_type == "daily_loss":
            message = f"""⚠️ <b>GÜNLÜK ZARAR LİMİTİ!</b>

🔴 <b>Risk Durumu:</b>
• Günlük Zarar: {self.format_percentage(current_value)}
• Limit: {self.format_percentage(limit_value)}
• Özkaynak: ${account_info.get('equity', 0):,.2f}

🛑 <b>Bugün için işlem durduruldu!</b>
Yarın yeni güne başlanacak."""
            
        elif risk_type == "margin":
            message = f"""⚠️ <b>MARJİN UYARISI!</b>

🔴 <b>Marjin Durumu:</b>
• Mevcut Seviye: {current_value:.1f}%
• Minimum Limit: {limit_value:.1f}%
• Serbest Marjin: ${account_info.get('margin_free', 0):,.2f}

🛑 <b>Yeni işlem yapılamıyor!</b>"""
        
        else:
            return
        
        self.send_message(message)
    
    def send_market_filter_notification(self, filter_type: str, details: str = ""):
        """Market filtre bildirimi (sessiz)"""
        # Market filtre bildirimlerini sessiz gönder - çok sık olabilir
        if filter_type == "trading_hours":
            message = f"🕐 Market saatleri dışında - İşlem bekleniyor"
        elif filter_type == "volatility":
            message = f"📊 Yüksek volatilite tespit edildi - Güvenlik için bekleniyor"
        elif filter_type == "spread":
            message = f"📈 Yüksek spread - İşlem için uygun koşullar bekleniyor"
        else:
            return
        
        # Bu bildirimleri sessiz ve sadece önemli durumlarda gönder
        # Şimdilik kapalı - çok spam olabilir
        # self.send_message(message, disable_notification=True)
    
    def send_error_notification(self, error_type: str, error_message: str):
        """Hata bildirimi"""
        if not self.send_error_notifications:
            return
        
        message = f"""🚨 <b>BOT HATASI!</b>

❌ <b>Hata Türü:</b> {error_type}
📝 <b>Detay:</b> {error_message}
🕐 <b>Zaman:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

<i>Bot çalışmaya devam etmeye çalışıyor...</i>"""
        
        self.send_message(message)
    
    def send_daily_summary(self, summary_data: Dict):
        """Günlük özet bildirimi"""
        if not self.send_daily_summary:
            return
        
        total_trades = summary_data.get('total_trades', 0)
        winning_trades = summary_data.get('winning_trades', 0)
        losing_trades = summary_data.get('losing_trades', 0)
        daily_pnl = summary_data.get('daily_pnl', 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Günlük sonuca göre emoji
        emoji = "🎉" if daily_pnl > 0 else "😔" if daily_pnl < 0 else "😐"
        
        message = f"""{emoji} <b>GÜNLÜK ÖZET</b>

📊 <b>İşlem Performansı:</b>
• Toplam İşlem: {total_trades}
• Kazanan: {winning_trades} ✅
• Kaybeden: {losing_trades} ❌
• Başarı Oranı: {win_rate:.1f}%

💰 <b>Finansal Durum:</b>
• Günlük P&L: ${daily_pnl:+.2f}
• Toplam Bakiye: ${summary_data.get('balance', 0):,.2f}
• Özkaynak: ${summary_data.get('equity', 0):,.2f}

📈 <b>Risk Metrikleri:</b>
• Max Drawdown: {summary_data.get('max_drawdown', 0):.2f}%
• Marjin Seviyesi: {summary_data.get('margin_level', 0):.1f}%

<i>Tarih: {datetime.now().strftime('%d.%m.%Y')}</i>"""
        
        self.send_message(message)
    
    def send_strong_signal_notification(self, signal_data: Dict):
        """Güçlü sinyal bildirimi"""
        if signal_data.get('strength', 0) >= 7:  # Sadece çok güçlü sinyaller
            emoji = "🚀" if "BUY" in signal_data.get('signal', '') else "⚡"
            
            message = f"""{emoji} <b>GÜÇLÜ SİNYAL TESPİT EDİLDİ!</b>

📊 <b>Sinyal Detayları:</b>
• Tip: {signal_data.get('signal', 'N/A')}
• Güç: {signal_data.get('strength', 0)}/10 ⭐
• Fiyat: {self.format_price(signal_data.get('price', 0))}

🔍 <b>Teknik Durum:</b>
• RSI: {signal_data.get('rsi', 0):.1f}
• SuperTrend: {'Yükseliş' if signal_data.get('trend', 0) == 1 else 'Düşüş'}
• MACD: {'Pozitif' if signal_data.get('macd_signal') else 'Negatif'}

<i>Güçlü sinyal - Dikkat!</i>"""
            
            self.send_message(message)
    
    def send_connection_status(self, status: str, details: str = ""):
        """Bağlantı durumu bildirimi"""
        if status == "connected":
            message = f"✅ MT5 bağlantısı yeniden kuruldu"
        elif status == "disconnected":
            message = f"❌ MT5 bağlantısı kesildi - Yeniden bağlanmaya çalışılıyor..."
        elif status == "reconnecting":
            message = f"🔄 MT5 yeniden bağlanma denemesi..."
        else:
            return
        
        if details:
            message += f"\n<i>{details}</i>"
        
        self.send_message(message)

# Test fonksiyonu
def test_telegram_notifications():
    """Telegram bildirimlerini test et"""
    BOT_TOKEN = "7594813856:AAGYoqUnHkT6Mybo7L3goS-Rw_7dJ8bnRpU"
    CHAT_ID = "6694433256"
    
    notifier = TelegramNotifier(BOT_TOKEN, CHAT_ID)
    
    # Test mesajları
    print("Telegram bildirimleri test ediliyor...")
    
    # 1. Başlangıç bildirimi
    account_info = {
        'login': 12345678,
        'balance': 10000.0,
        'equity': 10000.0,
        'margin_level': 0.0
    }
    notifier.send_startup_notification(account_info)
    
    # 2. İşlem bildirimi
    signal_data = {
        'signal': 'STRONG_BUY',
        'strength': 8,
        'rsi': 25.5,
        'macd_signal': True,
        'bb_position': 'lower'
    }
    notifier.send_trade_notification(signal_data, "BUY", 2650.50, 2645.00, 2660.00, 0.01)
    
    print("Test mesajları gönderildi!")

if __name__ == "__main__":
    test_telegram_notifications()