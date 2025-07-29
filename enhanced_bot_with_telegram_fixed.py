import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime, timedelta
import talib
import sqlite3
import json
from typing import Dict, List, Optional, Tuple
import warnings
import urllib.request
import urllib.parse
warnings.filterwarnings('ignore')

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhanced_bot_telegram.log'),
        logging.StreamHandler()
    ]
)

class TelegramNotifier:
    """Telegram Bildirim Sınıfı - urllib kullanarak"""
    
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
        
        # Test bağlantısı - sadece bir kere
        self.test_connection()
    
    def test_connection(self):
        """Telegram bağlantısını test et"""
        try:
            url = f"{self.api_url}/getMe"
            with urllib.request.urlopen(url, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('ok'):
                    bot_info = result['result']
                    self.logger.info(f"Telegram bağlantısı başarılı: @{bot_info['username']}")
                    return True
            self.logger.error("Telegram bağlantısı başarısız")
            return False
        except Exception as e:
            self.logger.error(f"Telegram test hatası: {e}")
            return False
    
    def send_message(self, message: str, parse_mode: str = "HTML", disable_notification: bool = False):
        """Telegram mesajı gönder"""
        try:
            url = f"{self.api_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_notification': disable_notification
            }
            
            data_encoded = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=data_encoded, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                if result.get('ok'):
                    return True
                else:
                    self.logger.error(f"Telegram mesaj hatası: {result}")
                    
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

class EnhancedRiskManager:
    """Gelişmiş Risk Yönetimi Sınıfı"""
    
    def __init__(self, initial_balance: float, max_drawdown_percent: float = 20.0, 
                 daily_loss_limit_percent: float = 5.0):
        self.initial_balance = initial_balance
        self.max_drawdown_percent = max_drawdown_percent
        self.daily_loss_limit_percent = daily_loss_limit_percent
        self.daily_start_balance = initial_balance
        self.peak_balance = initial_balance
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
    def check_drawdown(self, current_equity: float) -> bool:
        """Maksimum drawdown kontrolü"""
        current_drawdown = (self.peak_balance - current_equity) / self.peak_balance * 100
        if current_drawdown > self.max_drawdown_percent:
            return False
        
        # Peak balance güncelle
        if current_equity > self.peak_balance:
            self.peak_balance = current_equity
            
        return True
    
    def check_daily_loss_limit(self, current_equity: float) -> bool:
        """Günlük zarar limiti kontrolü"""
        # Gün değişti mi kontrol et
        current_time = datetime.now()
        if current_time.date() > self.daily_reset_time.date():
            self.reset_daily_balance(current_equity)
            
        daily_loss = (self.daily_start_balance - current_equity) / self.daily_start_balance * 100
        if daily_loss > self.daily_loss_limit_percent:
            return False
        return True
    
    def reset_daily_balance(self, current_equity: float):
        """Günlük başlangıç bakiyesini sıfırla"""
        self.daily_start_balance = current_equity
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

class MarketConditionAnalyzer:
    """Market Koşulları Analiz Sınıfı"""
    
    @staticmethod
    def check_volatility_filter(df: pd.DataFrame, volatility_threshold: float = 2.0) -> bool:
        """Volatilite filtresi"""
        if len(df) < 20:
            return True
            
        atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values, 14)
        if len(atr) < 20:
            return True
            
        current_atr = atr[-1]
        avg_atr = np.mean(atr[-20:])
        
        if current_atr > avg_atr * volatility_threshold:
            return False
        return True
    
    @staticmethod
    def is_trading_time() -> bool:
        """Major market saatleri kontrolü"""
        current_time = datetime.utcnow()
        hour = current_time.hour
        weekday = current_time.weekday()
        
        # Hafta sonu kontrolü
        if weekday >= 5:
            return False
        
        # London: 08:00-17:00 GMT, New York: 13:00-22:00 GMT
        london_session = 8 <= hour <= 17
        ny_session = 13 <= hour <= 22
        
        return london_session or ny_session
    
    @staticmethod
    def check_spread_filter(symbol: str, max_spread_points: int = 20) -> bool:
        """Spread filtresi"""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return False
        
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return False
            
        spread = tick.ask - tick.bid
        spread_points = spread / symbol_info.point
        
        if spread_points > max_spread_points:
            return False
        return True

class DatabaseManager:
    """Veritabanı Yönetim Sınıfı"""
    
    def __init__(self, db_path: str = "enhanced_trading_bot_telegram.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Veritabanı tablolarını oluştur"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                symbol TEXT,
                signal_type TEXT,
                signal_strength INTEGER,
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                lot_size REAL,
                result TEXT,
                profit_loss REAL,
                duration_minutes INTEGER,
                rsi_value REAL,
                macd_signal TEXT,
                bb_position TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_trade(self, trade_data: Dict):
        """İşlem verisini kaydet"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trades (timestamp, symbol, signal_type, signal_strength, 
                                  entry_price, stop_loss, take_profit, lot_size,
                                  rsi_value, macd_signal, bb_position)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data['timestamp'], trade_data['symbol'], trade_data['signal_type'],
                trade_data['signal_strength'], trade_data['entry_price'], 
                trade_data['stop_loss'], trade_data['take_profit'], trade_data['lot_size'],
                trade_data.get('rsi_value'), trade_data.get('macd_signal'), trade_data.get('bb_position')
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Veritabanı kayıt hatası: {e}")

class EnhancedMegaTrendBotWithTelegram:
    def __init__(self, symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M5, lot_size=0.01,
                 telegram_bot_token=None, telegram_chat_id=None):
        # Orijinal parametreler
        self.symbol = symbol
        self.timeframe = timeframe
        self.lot_size = lot_size
        self.magic_number = 1234544
        self.max_positions = 3
        self.min_margin_level = 50.0
        self.min_signal_strength = 2
        
        # DEMA parametreleri
        self.media1_period = 20
        self.media2_period = 50
        self.media3_period = 200
        
        # ATR parametreleri
        self.atr_period = 10
        self.atr_multiplier = 1.0
        
        # Pivot parametreleri
        self.pivot_period = 10
        self.max_num_pivot = 20
        self.channel_width = 10
        self.max_num_sr = 5
        self.min_strength = 2
        self.supply_demand_threshold = 10.0
        self.resolution_div = 50
        self.pivot_proximity_threshold = 0.002
        
        # Cache
        self.last_signal = None
        self.last_signal_time = None
        self.last_data_time = None
        self.data_cache = None
        
        # Logger
        self.logger = logging.getLogger(__name__)
        
        # Telegram bildirimi - sadece test, henüz mesaj gönderme
        if telegram_bot_token and telegram_chat_id:
            self.telegram = TelegramNotifier(telegram_bot_token, telegram_chat_id)
        else:
            self.telegram = None
            self.logger.warning("Telegram bilgileri eksik - Bildirimler kapalı")
        
        # Gelişmiş bileşenler - MT5 bağlantısı olmadan
        self.initialize_enhanced_components()
    
    def initialize_enhanced_components(self):
        """Gelişmiş bileşenleri başlat - MT5 bağlantısı yapmadan"""
        try:
            # Varsayılan bakiye - gerçek bakiye run_bot() içinde alınacak
            initial_balance = 10000  # Varsayılan değer
            
            self.risk_manager = EnhancedRiskManager(initial_balance)
            self.market_analyzer = MarketConditionAnalyzer()
            self.db_manager = DatabaseManager()
            
            self.logger.info("Gelişmiş bileşenler başarıyla başlatıldı")
        except Exception as e:
            self.logger.error(f"Gelişmiş bileşenler başlatılırken hata: {e}")
            if self.telegram:
                self.telegram.send_error_notification("Bileşen Başlatma", str(e))

    def initialize_mt5(self):
        """MT5 bağlantısını başlat"""
        for attempt in range(3):
            if mt5.initialize():
                account_info = mt5.account_info()
                if account_info is not None:
                    self.logger.info(f"MT5 bağlantısı başarılı - Hesap: {account_info.login}, Bakiye: {account_info.balance}")
                    
                    # Risk manager'ı gerçek bakiye ile güncelle
                    self.risk_manager.initial_balance = account_info.balance
                    self.risk_manager.daily_start_balance = account_info.balance
                    self.risk_manager.peak_balance = account_info.balance
                    
                    # Telegram başlangıç bildirimi - sadece bir kere
                    if self.telegram:
                        account_dict = {
                            'login': account_info.login,
                            'balance': account_info.balance,
                            'equity': account_info.equity,
                            'margin_level': account_info.margin_level
                        }
                        self.telegram.send_startup_notification(account_dict)
                    
                    return True
                self.logger.error(f"Hesap bilgileri alınamadı, deneme {attempt + 1}/3")
                mt5.shutdown()
                time.sleep(2)
            else:
                self.logger.error(f"MT5 başlatılamadı, deneme {attempt + 1}/3")
                time.sleep(2)
        return False

    def get_data(self, bars=500):
        """Piyasa verilerini al"""
        current_time = datetime.now()
        if self.data_cache is not None and self.last_data_time is not None:
            bar_duration = timedelta(minutes=5 if self.timeframe == mt5.TIMEFRAME_M5 else 1)
            if current_time - self.last_data_time < bar_duration:
                return self.data_cache
        
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            self.logger.error("Veri alınamadı")
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        self.data_cache = df
        self.last_data_time = current_time
        return df

    def calculate_dema(self, data, period):
        """Double Exponential Moving Average hesapla"""
        ema1 = data.ewm(span=period).mean()
        ema2 = ema1.ewm(span=period).mean()
        return 2 * ema1 - ema2

    def calculate_supertrend(self, df):
        """SuperTrend indikatörünü hesapla"""
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        atr = talib.ATR(high, low, close, timeperiod=self.atr_period)
        hl2 = (high + low) / 2
        up = hl2 - (self.atr_multiplier * atr)
        down = hl2 + (self.atr_multiplier * atr)
        trend = np.zeros(len(close))
        supertrend = np.zeros(len(close))
        
        for i in range(1, len(close)):
            up[i] = max(up[i], up[i-1]) if close[i-1] > up[i-1] else up[i]
            down[i] = min(down[i], down[i-1]) if close[i-1] < down[i-1] else down[i]
            trend[i] = 1 if close[i] > down[i-1] else (-1 if close[i] < up[i-1] else trend[i-1])
            supertrend[i] = up[i] if trend[i] == 1 else down[i]
        
        return trend, supertrend

    def calculate_enhanced_indicators(self, df):
        """Gelişmiş teknik indikatörleri hesapla"""
        indicators = {}
        
        try:
            # RSI
            indicators['rsi'] = talib.RSI(df['close'].values, timeperiod=14)
            
            # MACD
            macd, macd_signal, macd_hist = talib.MACD(df['close'].values)
            indicators['macd'] = macd
            indicators['macd_signal'] = macd_signal
            indicators['macd_hist'] = macd_hist
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = talib.BBANDS(df['close'].values, timeperiod=20, nbdevup=2, nbdevdn=2)
            indicators['bb_upper'] = bb_upper
            indicators['bb_middle'] = bb_middle
            indicators['bb_lower'] = bb_lower
            
        except Exception as e:
            self.logger.error(f"İndikatör hesaplama hatası: {e}")
            
        return indicators

    def find_pivot_points(self, df):
        """Pivot noktalarını bul"""
        high = df['high'].values
        low = df['low'].values
        pivot_highs = []
        pivot_lows = []
        
        for i in range(self.pivot_period, len(high) - self.pivot_period):
            is_pivot_high = all(high[j] < high[i] for j in range(i - self.pivot_period, i + self.pivot_period + 1) if j != i)
            if is_pivot_high:
                pivot_highs.append((i, high[i]))
            
            is_pivot_low = all(low[j] > low[i] for j in range(i - self.pivot_period, i + self.pivot_period + 1) if j != i)
            if is_pivot_low:
                pivot_lows.append((i, low[i]))
        
        return pivot_highs, pivot_lows

    def calculate_support_resistance(self, pivot_highs, pivot_lows, df):
        """Destek ve direnç seviyelerini hesapla"""
        all_pivots = [(idx, price, 'high') for idx, price in pivot_highs]
        all_pivots.extend([(idx, price, 'low') for idx, price in pivot_lows])
        all_pivots.sort(key=lambda x: x[0], reverse=True)
        
        pivot_prices = [p[1] for p in all_pivots[:self.max_num_pivot]]
        price_range = df['high'].max() - df['low'].min()
        channel_width = price_range * self.channel_width / 100
        
        support_resistance_levels = []
        for price in pivot_prices:
            strength = sum(1 for p in pivot_prices if abs(p - price) <= channel_width)
            if strength >= self.min_strength:
                level_high = max(p for p in pivot_prices if abs(p - price) <= channel_width)
                level_low = min(p for p in pivot_prices if abs(p - price) <= channel_width)
                support_resistance_levels.append({
                    'level': (level_high + level_low) / 2,
                    'strength': strength,
                    'high': level_high,
                    'low': level_low
                })
        
        return sorted(support_resistance_levels, key=lambda x: x['strength'], reverse=True)[:self.max_num_sr]

    def enhanced_risk_check(self) -> bool:
        """Gelişmiş risk kontrolü"""
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("Hesap bilgileri alınamadı")
            return False
        
        # Temel marjin kontrolü
        margin_level = account_info.margin_level
        if margin_level != 0.0 and margin_level < self.min_margin_level:
            self.logger.warning(f"Marjin seviyesi yetersiz: {margin_level}%")
            if self.telegram:
                account_dict = {
                    'balance': account_info.balance,
                    'equity': account_info.equity,
                    'margin_free': account_info.margin_free
                }
                self.telegram.send_risk_notification("margin", margin_level, self.min_margin_level, account_dict)
            return False
        
        # Drawdown kontrolü
        if not self.risk_manager.check_drawdown(account_info.equity):
            if self.telegram:
                current_drawdown = (self.risk_manager.peak_balance - account_info.equity) / self.risk_manager.peak_balance * 100
                account_dict = {
                    'balance': account_info.balance,
                    'equity': account_info.equity
                }
                self.telegram.send_risk_notification("drawdown", current_drawdown, self.risk_manager.max_drawdown_percent, account_dict)
            return False
        
        # Günlük zarar limiti kontrolü
        if not self.risk_manager.check_daily_loss_limit(account_info.equity):
            if self.telegram:
                daily_loss = (self.risk_manager.daily_start_balance - account_info.equity) / self.risk_manager.daily_start_balance * 100
                account_dict = {
                    'equity': account_info.equity
                }
                self.telegram.send_risk_notification("daily_loss", daily_loss, self.risk_manager.daily_loss_limit_percent, account_dict)
            return False
        
        # Spread kontrolü
        if not self.market_analyzer.check_spread_filter(self.symbol):
            return False
        
        return True

    def enhanced_market_filter(self, df: pd.DataFrame) -> bool:
        """Gelişmiş market filtresi"""
        # Trading saatleri kontrolü
        if not self.market_analyzer.is_trading_time():
            return False
        
        # Volatilite filtresi
        if not self.market_analyzer.check_volatility_filter(df):
            return False
        
        return True

    def generate_enhanced_signals(self, df):
        """Gelişmiş sinyal üretimi"""
        if len(df) < self.media3_period:
            return None
        
        # Orijinal sinyal mantığı
        close = df['close'].values
        dema1 = self.calculate_dema(df['close'], self.media1_period)
        dema2 = self.calculate_dema(df['close'], self.media2_period)
        dema3 = self.calculate_dema(df['close'], self.media3_period)
        
        trend, supertrend = self.calculate_supertrend(df)
        pivot_highs, pivot_lows = self.find_pivot_points(df)
        sr_levels = self.calculate_support_resistance(pivot_highs, pivot_lows, df)
        
        # Gelişmiş indikatörler
        indicators = self.calculate_enhanced_indicators(df)
        
        current_price = close[-1]
        previous_price = close[-2]
        current_time = df['time'].iloc[-1]
        
        signal = None
        signal_strength = 0
        
        # SuperTrend sinyali
        if len(trend) > 1:
            if trend[-1] == 1 and trend[-2] == -1:
                signal = "BUY"
                signal_strength += 3
            elif trend[-1] == -1 and trend[-2] == 1:
                signal = "SELL"
                signal_strength += 3
        
        # DEMA sinyali
        if len(dema1) > 1 and len(dema2) > 1 and len(dema3) > 1:
            ma1_current = dema1.iloc[-1]
            ma2_current = dema2.iloc[-1]
            ma3_current = dema3.iloc[-1]
            
            if ma1_current > ma2_current > ma3_current and current_price > ma1_current:
                signal = "BUY" if signal is None else signal
                signal_strength += 2 if signal == "BUY" else 1
            elif ma1_current < ma2_current < ma3_current and current_price < ma1_current:
                signal = "SELL" if signal is None else signal
                signal_strength += 2 if signal == "SELL" else 1
        
        # RSI konfirmasyonu
        if 'rsi' in indicators and len(indicators['rsi']) > 0:
            current_rsi = indicators['rsi'][-1]
            if signal == "BUY" and current_rsi < 30:
                signal_strength += 2
            elif signal == "BUY" and current_rsi < 50:
                signal_strength += 1
            elif signal == "SELL" and current_rsi > 70:
                signal_strength += 2
            elif signal == "SELL" and current_rsi > 50:
                signal_strength += 1
        
        # MACD konfirmasyonu
        if ('macd' in indicators and 'macd_signal' in indicators and 
            len(indicators['macd']) > 1 and len(indicators['macd_signal']) > 1):
            macd = indicators['macd']
            macd_signal_line = indicators['macd_signal']
            
            if signal == "BUY" and macd[-1] > macd_signal_line[-1] and macd[-2] <= macd_signal_line[-2]:
                signal_strength += 2
            elif signal == "SELL" and macd[-1] < macd_signal_line[-1] and macd[-2] >= macd_signal_line[-2]:
                signal_strength += 2
        
        # Bollinger Bands konfirmasyonu
        if ('bb_upper' in indicators and 'bb_lower' in indicators and 
            len(indicators['bb_upper']) > 0 and len(indicators['bb_lower']) > 0):
            bb_upper = indicators['bb_upper'][-1]
            bb_lower = indicators['bb_lower'][-1]
            
            if signal == "BUY" and current_price <= bb_lower:
                signal_strength += 1
            elif signal == "SELL" and current_price >= bb_upper:
                signal_strength += 1
        
        # Sinyal tekrar kontrolü
        if (self.last_signal_time is not None and
            self.last_signal == signal and
            (current_time - self.last_signal_time).total_seconds() < 300):
            return None
        
        if signal and signal_strength >= self.min_signal_strength:
            self.last_signal = signal
            self.last_signal_time = current_time
            
            # Sinyal verisini hazırla
            signal_data = {
                'signal': signal,
                'strength': signal_strength,
                'price': current_price,
                'ma1': dema1.iloc[-1],
                'ma2': dema2.iloc[-1],
                'ma3': dema3.iloc[-1],
                'supertrend': supertrend[-1],
                'trend': trend[-1],
                'sr_levels': sr_levels,
                'rsi': indicators.get('rsi', [None])[-1] if 'rsi' in indicators else None,
                'macd_signal': (indicators['macd'][-1] > indicators['macd_signal'][-1] 
                               if 'macd' in indicators and len(indicators['macd']) > 0 else None),
                'bb_position': ('upper' if current_price >= indicators['bb_upper'][-1] 
                               else 'lower' if current_price <= indicators['bb_lower'][-1] 
                               else 'middle' if 'bb_upper' in indicators else None)
            }
            
            # Güçlü sinyal bildirimi
            if self.telegram and signal_strength >= 7:
                self.telegram.send_strong_signal_notification(signal_data)
            
            return signal_data
        
        return None

    def calculate_stop_loss_take_profit(self, signal_data):
        """Stop Loss ve Take Profit hesapla"""
        current_price = signal_data['price']
        signal = signal_data['signal']
        atr = self.get_atr()
        
        if signal in ["BUY", "STRONG_BUY"]:
            stop_loss = current_price - (2 * atr)
            take_profit = current_price + (3 * atr)
            
            # SR seviyelerine göre SL optimizasyonu
            for level in signal_data.get('sr_levels', []):
                if level['level'] < current_price:
                    stop_loss = max(stop_loss, level['level'] - 0.0005)
                    break
                    
        elif signal in ["SELL", "STRONG_SELL"]:
            stop_loss = current_price + (2 * atr)
            take_profit = current_price - (3 * atr)
            
            # SR seviyelerine göre SL optimizasyonu
            for level in signal_data.get('sr_levels', []):
                if level['level'] > current_price:
                    stop_loss = min(stop_loss, level['level'] + 0.0005)
                    break
        else:
            return None, None
        
        return stop_loss, take_profit

    def get_atr(self):
        """ATR değerini al"""
        df = self.get_data(50)
        if df is None:
            return 0.001
        atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=self.atr_period)
        return atr[-1] if len(atr) > 0 else 0.001

    def count_positions(self, position_type):
        """Pozisyon sayısını say"""
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return 0
        return sum(1 for pos in positions if pos.magic == self.magic_number and pos.type == position_type)

    def place_order(self, order_type, stop_loss, take_profit, lot_size=None):
        """Emir ver"""
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            self.logger.error(f"Symbol bilgisi alınamadı: {self.symbol}")
            return False
        
        if not symbol_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                self.logger.error(f"Symbol seçilemedi: {self.symbol}")
                return False
        
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            self.logger.error("Tick bilgisi alınamadı")
            return False
        
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        volume = max(symbol_info.volume_min, min(symbol_info.volume_max, lot_size or self.lot_size))
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 20,
            "magic": self.magic_number,
            "comment": "EnhancedMegaTrendBot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Emir başarısız: {result.retcode if result else 'None'}")
            if self.telegram:
                self.telegram.send_error_notification("Emir Hatası", f"Retcode: {result.retcode if result else 'None'}")
            return False
        
        self.logger.info(f"Emir başarılı: {'BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL'} - {volume} lot")
        return True

    def save_trade_to_db(self, signal_data: Dict, entry_price: float, sl: float, tp: float):
        """İşlemi veritabanına kaydet"""
        trade_data = {
            'timestamp': datetime.now(),
            'symbol': self.symbol,
            'signal_type': signal_data['signal'],
            'signal_strength': signal_data['strength'],
            'entry_price': entry_price,
            'stop_loss': sl,
            'take_profit': tp,
            'lot_size': self.lot_size,
            'rsi_value': signal_data.get('rsi'),
            'macd_signal': str(signal_data.get('macd_signal')),
            'bb_position': signal_data.get('bb_position')
        }
        self.db_manager.save_trade(trade_data)

    def close_positions(self, position_type=None):
        """Pozisyonları kapat"""
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return True
        
        for position in positions:
            if position.magic != self.magic_number or (position_type is not None and position.type != position_type):
                continue
            
            order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(self.symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(self.symbol).ask
            
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": position.volume,
                "type": order_type,
                "position": position.ticket,
                "price": price,
                "deviation": 20,
                "magic": self.magic_number,
                "comment": "Close by EnhancedBot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(close_request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"Pozisyon kapatıldı: {position.ticket}")
            else:
                self.logger.error(f"Pozisyon kapatılamadı: {result.comment}")

    def run_bot(self):
        """Ana bot döngüsü"""
        self.logger.info("Gelişmiş MegaTrend Bot (Telegram) başlatıldı...")
        
        # MT5 bağlantısını başlat - sadece burada bir kere
        if not self.initialize_mt5():
            self.logger.error("Bot başlatılamadı. Program sonlandırılıyor.")
            if self.telegram:
                self.telegram.send_error_notification("MT5 Bağlantı", "MT5 başlatılamadı")
            return
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                
                # Her 500 döngüde bir durum bildirimi
                if cycle_count % 500 == 0:
                    account_info = mt5.account_info()
                    if account_info:
                        self.logger.info(f"Döngü #{cycle_count} - Bakiye: {account_info.balance:.2f}, Özkaynak: {account_info.equity:.2f}")
                
                # Veri al
                df = self.get_data()
                if df is None:
                    time.sleep(5)
                    continue
                
                # Market filtrelerini kontrol et
                if not self.enhanced_market_filter(df):
                    time.sleep(30)
                    continue
                
                # Risk kontrolü
                if not self.enhanced_risk_check():
                    self.logger.warning("Risk kontrolü başarısız - 60 saniye bekleniyor")
                    time.sleep(60)
                    continue
                
                # Sinyal üret
                signal_data = self.generate_enhanced_signals(df)
                if signal_data is None:
                    time.sleep(5)
                    continue
                
                signal = signal_data['signal']
                strength = signal_data['strength']
                
                self.logger.info(f"Sinyal tespit edildi: {signal} (Güç: {strength})")
                
                # Pozisyon sayılarını kontrol et
                buy_count = self.count_positions(mt5.POSITION_TYPE_BUY)
                sell_count = self.count_positions(mt5.POSITION_TYPE_SELL)
                
                # BUY sinyali
                if signal in ["BUY", "STRONG_BUY"] and buy_count < self.max_positions:
                    lot_size = self.lot_size if buy_count == 0 else self.lot_size / 2
                    sl, tp = self.calculate_stop_loss_take_profit(signal_data)
                    
                    if sl is None or tp is None:
                        time.sleep(5)
                        continue
                    
                    # Güçlü sinyal varsa ters pozisyonları kapat
                    if sell_count > 0 and signal == "STRONG_BUY":
                        self.close_positions(mt5.POSITION_TYPE_SELL)
                        self.logger.info("STRONG_BUY sinyali - SELL pozisyonları kapatıldı")
                    
                    if self.place_order(mt5.ORDER_TYPE_BUY, sl, tp, lot_size):
                        self.logger.info(f"BUY emri başarılı - SL: {sl:.5f}, TP: {tp:.5f}")
                        
                        # Telegram bildirimi
                        if self.telegram:
                            self.telegram.send_trade_notification(signal_data, "BUY", signal_data['price'], sl, tp, lot_size)
                        
                        # Veritabanına kaydet
                        self.save_trade_to_db(signal_data, signal_data['price'], sl, tp)
                
                # SELL sinyali
                elif signal in ["SELL", "STRONG_SELL"] and sell_count < self.max_positions:
                    lot_size = self.lot_size if sell_count == 0 else self.lot_size / 2
                    sl, tp = self.calculate_stop_loss_take_profit(signal_data)
                    
                    if sl is None or tp is None:
                        time.sleep(5)
                        continue
                    
                    # Güçlü sinyal varsa ters pozisyonları kapat
                    if buy_count > 0 and signal == "STRONG_SELL":
                        self.close_positions(mt5.POSITION_TYPE_BUY)
                        self.logger.info("STRONG_SELL sinyali - BUY pozisyonları kapatıldı")
                    
                    if self.place_order(mt5.ORDER_TYPE_SELL, sl, tp, lot_size):
                        self.logger.info(f"SELL emri başarılı - SL: {sl:.5f}, TP: {tp:.5f}")
                        
                        # Telegram bildirimi
                        if self.telegram:
                            self.telegram.send_trade_notification(signal_data, "SELL", signal_data['price'], sl, tp, lot_size)
                        
                        # Veritabanına kaydet
                        self.save_trade_to_db(signal_data, signal_data['price'], sl, tp)
                
                time.sleep(5)
                
            except KeyboardInterrupt:
                self.logger.info("Bot kullanıcı tarafından durduruldu...")
                if self.telegram:
                    self.telegram.send_message("🛑 <b>Bot Durduruldu</b>\n\nBot kullanıcı tarafından durduruldu.")
                break
            except Exception as e:
                self.logger.error(f"Bot döngüsünde hata: {str(e)}")
                if self.telegram:
                    self.telegram.send_error_notification("Bot Döngüsü", str(e))
                time.sleep(10)
        
        mt5.shutdown()
        self.logger.info("Gelişmiş MegaTrend Bot (Telegram) kapatıldı.")

if __name__ == "__main__":
    try:
        # Telegram bilgileri
        BOT_TOKEN = "7594813856:AAGYoqUnHkT6Mybo7L3goS-Rw_7dJ8bnRpU"
        CHAT_ID = "6694433256"
        
        # Bot parametrelerini ayarla
        bot = EnhancedMegaTrendBotWithTelegram(
            symbol="XAUUSD", 
            timeframe=mt5.TIMEFRAME_M5, 
            lot_size=0.01,
            telegram_bot_token=BOT_TOKEN,
            telegram_chat_id=CHAT_ID
        )
        
        # Botu başlat
        bot.run_bot()
        
    except Exception as e:
        logging.error(f"Bot başlatma hatası: {e}")
        print(f"HATA: {e}")
        input("Çıkmak için Enter tuşuna basın...")