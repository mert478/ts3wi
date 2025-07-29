import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime, timedelta
import talib
import warnings
import json
import os
import requests
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
warnings.filterwarnings('ignore')

# Gelişmiş loglama yapılandırması
import sys
import locale

# Windows encoding sorununu çöz
if sys.platform.startswith('win'):
    # UTF-8 encoding'i zorla
    sys.stdout.reconfigure(encoding='utf-8', errors='ignore')
    sys.stderr.reconfigure(encoding='utf-8', errors='ignore')

# Unicode-safe logging yapılandırması
class UnicodeFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding='utf-8', delay=False):
        super().__init__(filename, mode, encoding, delay)

class UnicodeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            # Emoji'leri güvenli karakterlerle değiştir
            emoji_map = {
                '🚀': '[START]',
                '🎯': '[TARGET]',
                '❌': '[X]',
                '✅': '[OK]',
                '🔍': '[SEARCH]',
                '💰': '[MONEY]',
                '📊': '[CHART]',
                '⚡': '[POWER]',
                '📈': '[UP]',
                '🛡️': '[SHIELD]',
                '⏰': '[TIME]',
                '🔒': '[LOCK]',
                '🔥': '[FIRE]',
                '💎': '[DIAMOND]',
                '🏆': '[TROPHY]',
                '📉': '[DOWN]',
                '💵': '[DOLLAR]',
                '⏹️': '[STOP]',
                '👋': '[WAVE]',
                '💪': '[STRONG]'
            }
            
            for emoji, replacement in emoji_map.items():
                msg = msg.replace(emoji, replacement)
            
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except (UnicodeEncodeError, UnicodeDecodeError):
            # Emoji'ler çıkarılmış basit mesaj
            try:
                simple_msg = ''.join(char for char in record.getMessage() if ord(char) < 128)
                stream = self.stream
                stream.write(f"{record.levelname}: {simple_msg}\n")
                self.flush()
            except:
                pass

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        UnicodeFileHandler('bot.log', encoding='utf-8'),
        UnicodeStreamHandler()
    ]
)

@dataclass
class TradeRecord:
    """Trade kayıt yapısı"""
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    signal_type: str = ""
    signal_strength: int = 0
    lot_size: float = 0.0
    pnl: float = 0.0
    position_ticket: int = 0
    stop_loss: float = 0.0
    take_profit: float = 0.0

class PerformanceTracker:
    """Performans takip sistemi"""
    
    def __init__(self, data_file="performance_data.json"):
        self.data_file = data_file
        self.trades: List[TradeRecord] = []
        self.daily_pnl: Dict[str, float] = {}
        self.load_data()
        
    def load_data(self):
        """Kaydedilmiş verileri yükle"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.daily_pnl = data.get('daily_pnl', {})
                    # Trades verilerini TradeRecord'a dönüştür
                    trades_data = data.get('trades', [])
                    for trade_data in trades_data:
                        trade = TradeRecord(**trade_data)
                        self.trades.append(trade)
            except Exception as e:
                logging.error(f"Performance data yüklenemedi: {e}")
    
    def save_data(self):
        """Verileri kaydet"""
        try:
            data = {
                'daily_pnl': self.daily_pnl,
                'trades': [trade.__dict__ for trade in self.trades]
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, default=str, indent=2)
        except Exception as e:
                logging.error(f"Performance data kaydedilemedi: {e}")
    
    def log_trade_entry(self, trade_record: TradeRecord):
        """Trade girişini kaydet"""
        self.trades.append(trade_record)
        
    def log_trade_exit(self, position_ticket: int, exit_time: datetime, 
                      exit_price: float, pnl: float):
        """Trade çıkışını kaydet"""
        for trade in self.trades:
            if trade.position_ticket == position_ticket and trade.exit_time is None:
                trade.exit_time = exit_time
                trade.exit_price = exit_price
                trade.pnl = pnl
                
                # Günlük PnL güncelle
                day_key = exit_time.strftime('%Y-%m-%d')
                self.daily_pnl[day_key] = self.daily_pnl.get(day_key, 0) + pnl
                break
        self.save_data()
    
    def get_performance_metrics(self) -> Dict:
        """Performans metriklerini hesapla"""
        completed_trades = [t for t in self.trades if t.exit_time is not None]
        
        if not completed_trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'max_drawdown': 0
            }
        
        pnls = [trade.pnl for trade in completed_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        win_rate = len(wins) / len(completed_trades) if completed_trades else 0
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0
        profit_factor = (sum(wins) / abs(sum(losses))) if losses else float('inf')
        
        # Max drawdown hesaplama
        cumulative_pnl = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative_pnl)
        drawdown = running_max - cumulative_pnl
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
        
        return {
            'total_trades': len(completed_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_pnl': sum(pnls),
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_drawdown,
            'current_streak': self._calculate_current_streak(pnls)
        }
    
    def _calculate_current_streak(self, pnls: List[float]) -> int:
        """Mevcut kazanç/kayıp serisini hesapla"""
        if not pnls:
            return 0
        
        streak = 0
        last_positive = pnls[-1] > 0
        
        for pnl in reversed(pnls):
            if (pnl > 0) == last_positive:
                streak += 1
            else:
                break
        
        return streak if last_positive else -streak

class TelegramNotifier:
    """Telegram bildirimleri için sınıf"""
    
    def __init__(self, bot_token: str, chat_id: str, enabled: bool = True):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
    def send_message(self, message: str, parse_mode: str = "HTML"):
        """Telegram mesajı gönder"""
        if not self.enabled:
            return
        
        try:
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(self.base_url, data=payload, timeout=10)
            if response.status_code != 200:
                logging.warning(f"Telegram mesaj gönderilemedi: {response.status_code}")
        except Exception as e:
            logging.error(f"Telegram hata: {e}")
    
    def send_trade_signal(self, signal_data: dict):
        """Trade sinyali bildirimi"""
        signal = signal_data['signal']
        price = signal_data['price']
        strength = signal_data['strength']
        rsi = signal_data['rsi']
        trend = signal_data['trend_analysis']['direction']
        
        message = f"""
🎯 <b>YENİ SİNYAL</b> 🎯

📈 <b>Sinyal:</b> {signal}
💰 <b>Fiyat:</b> {price:.2f}
⚡ <b>Güç:</b> {strength}/10
📊 <b>RSI:</b> {rsi:.1f}
🔄 <b>Trend:</b> {trend}

⏰ <b>Zaman:</b> {datetime.now().strftime('%H:%M:%S')}
        """
        self.send_message(message)
    
    def send_trade_opened(self, order_type: str, lot_size: float, price: float, 
                         stop_loss: float, take_profit: float, ticket: int):
        """Açılan pozisyon bildirimi"""
        message = f"""
✅ <b>POZİSYON AÇILDI</b> ✅

📊 <b>Tip:</b> {order_type}
💎 <b>Lot:</b> {lot_size}
💰 <b>Giriş:</b> {price:.2f}
🛡️ <b>Stop Loss:</b> {stop_loss:.2f}
🎯 <b>Take Profit:</b> {take_profit:.2f}
🎫 <b>Ticket:</b> {ticket}

⏰ <b>Zaman:</b> {datetime.now().strftime('%H:%M:%S')}
        """
        self.send_message(message)
    
    def send_trade_closed(self, ticket: int, pnl: float, closing_price: float):
        """Kapatılan pozisyon bildirimi"""
        pnl_emoji = "💚" if pnl > 0 else "❌"
        message = f"""
{pnl_emoji} <b>POZİSYON KAPATILDI</b> {pnl_emoji}

🎫 <b>Ticket:</b> {ticket}
💰 <b>Kapanış:</b> {closing_price:.2f}
💵 <b>PnL:</b> ${pnl:.2f}

⏰ <b>Zaman:</b> {datetime.now().strftime('%H:%M:%S')}
        """
        self.send_message(message)
    
    def send_daily_summary(self, metrics: dict, account_info):
        """Günlük özet bildirimi"""
        message = f"""
📊 <b>GÜNLÜK ÖZET</b> 📊

💰 <b>Bakiye:</b> ${account_info.balance:.2f}
💎 <b>Equity:</b> ${account_info.equity:.2f}
📈 <b>Toplam İşlem:</b> {metrics['total_trades']}
🎯 <b>Kazanma Oranı:</b> {metrics['win_rate']:.1%}
💵 <b>Toplam PnL:</b> ${metrics['total_pnl']:.2f}

⏰ <b>Zaman:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}
        """
        self.send_message(message)

class ImprovedMegaTrendBot:
    def __init__(self, symbol="XAUUSD+", timeframe=mt5.TIMEFRAME_M15, 
                 initial_lot_size=0.01, risk_per_trade=0.02, 
                 enable_spread_filter=True, telegram_token=None, telegram_chat_id=None):
        
        # Unicode güvenli logging için emoji haritası
        self.emoji_map = {
            '🚀': '[START]', '🎯': '[TARGET]', '❌': '[X]', '✅': '[OK]',
            '🔍': '[SEARCH]', '💰': '[MONEY]', '📊': '[CHART]', '⚡': '[POWER]',
            '📈': '[UP]', '🛡️': '[SHIELD]', '⏰': '[TIME]', '🔒': '[LOCK]',
            '🔥': '[FIRE]', '💎': '[DIAMOND]', '🏆': '[TROPHY]', '📉': '[DOWN]',
            '💵': '[DOLLAR]', '⏹️': '[STOP]', '👋': '[WAVE]', '💪': '[STRONG]'
        }
        
        # Telegram bildirimleri
        self.telegram = TelegramNotifier(
            telegram_token, 
            telegram_chat_id, 
            enabled=(telegram_token is not None and telegram_chat_id is not None)
        )
        # Temel parametreler
        self.symbol = symbol
        self.timeframe = timeframe
        self.initial_lot_size = initial_lot_size
        self.risk_per_trade = risk_per_trade
        self.enable_spread_filter = enable_spread_filter
        self.magic_number = 1234544
        
        # Risk yönetimi parametreleri
        self.max_positions = 2  # Daha konservatif
        self.min_margin_level = 150.0  # Daha yüksek marjin
        self.max_spread = 15.0  # Daha dar spread
        self.max_lot_size = 0.5  # Daha küçük lot
        self.min_lot_size = 0.01
        self.max_daily_loss = 50.0  # Daha düşük günlük kayıp limiti
        self.max_drawdown_limit = 200.0  # Daha düşük drawdown limiti
        
        # ✨ ÇOK ESNEK SINYAL PARAMETRELERİ ✨
        self.min_signal_strength = 3  # ÇOK DÜŞÜK (önceki: 5)
        self.trend_confirmation_period = 15  # DAHA KISA (önceki: 20)
        self.false_signal_cooldown = 180  # 3 DAKİKA (önceki: 300)
        self.price_action_confirmation = False  # KAPALI (daha serbest)
        self.multi_timeframe_confirmation = False  # KAPALI
        self.momentum_filter = False  # KAPALI (daha serbest)
        self.volatility_breakout_filter = False  # KAPALI
        self.min_confirmations = 2  # ÇOK DÜŞÜK (önceki: 3)
        
        # Teknik analiz parametreleri (daha esnek)
        self.media1_period = 10  # DAHA KISA (önceki: 21)
        self.media2_period = 21  # DAHA KISA (önceki: 50)
        self.media3_period = 50   # DAHA KISA (önceki: 100)
        self.atr_period = 14     # STANDART (önceki: 21)
        self.atr_multiplier = 2.5  # DAHA DAR (önceki: 3.0)
        self.rsi_period = 14     # STANDART (önceki: 21)
        self.rsi_overbought = 70  # DAHA ESNEK (önceki: 75)
        self.rsi_oversold = 30   # DAHA ESNEK (önceki: 25)
        self.bb_period = 20      # STANDART (önceki: 21)
        self.bb_std = 2.0        # STANDART (önceki: 2.5)
        
        # MACD parametreleri
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        
        # Pivot ve S/R parametreleri (daha esnek)
        self.pivot_period = 10   # DAHA KISA (önceki: 20)
        self.max_num_pivot = 15  # DAHA FAZLA (önceki: 10)
        self.channel_width = 8   # DAHA GENİŞ (önceki: 5)
        self.max_num_sr = 5      # DAHA FAZLA (önceki: 3)
        self.min_strength = 2    # DAHA DÜŞÜK (önceki: 4)
        self.supply_demand_threshold = 15.0  # DAHA DÜŞÜK (önceki: 20.0)
        self.resolution_div = 30
        self.pivot_proximity_threshold = 0.001  # DAHA GENİŞ (önceki: 0.0005)
        
        # Trend analizi parametreleri (ultra esnek)
        self.min_trend_bars = 5   # ULTRA KISA (önceki: 10)
        self.trend_strength_threshold = 0.3  # ULTRA DÜŞÜK (önceki: 0.6)
        
        # Debug modu
        self.debug_mode = True  # Sinyal reddedilme sebeplerini göster
        self.signal_attempts = 0  # Sinyal denemesi sayacı
        
        # Adaptif parametreler
        self.adaptive_mode = True
        self.volatility_lookback = 30  # DAHA KISA (önceki: 50)
        
        # Cache ve tracking
        self.data_cache = None
        self.last_data_time = None
        self.last_signal = None
        self.last_signal_time = None
        self.support_levels = []
        self.resistance_levels = []
        self.supply_zones = []
        self.demand_zones = []
        
        # False signal prevention
        self.recent_signals = []
        self.signal_success_rate = {}
        self.consecutive_losses = 0
        self.max_consecutive_losses = 3  # Max 3 ardışık kayıp
        
        # Logger ve performance tracker
        self.logger = logging.getLogger(__name__)
        self.performance_tracker = PerformanceTracker()
        
        # Market filtresi
        self.market_hours = {
            'start': 0,
            'end': 23
        }
        
        self.initialize_mt5()

    def initialize_mt5(self) -> bool:
        """MT5 bağlantısını başlat"""
        for attempt in range(3):
            if mt5.initialize():
                account_info = mt5.account_info()
                if account_info is not None:
                    self.logger.info(f"MT5 bağlantısı başarılı - Hesap: {account_info.login}, "
                                   f"Bakiye: {account_info.balance}, Marjin Seviyesi: {account_info.margin_level}%")
                    
                    if not self._setup_symbol():
                        self.logger.error("Symbol kurulumu başarısız")
                        return False
                    
                    return True
                self.logger.error(f"Hesap bilgileri alınamadı, deneme {attempt + 1}/3")
                mt5.shutdown()
                time.sleep(2)
            else:
                self.logger.error(f"MT5 başlatılamadı, deneme {attempt + 1}/3")
                time.sleep(2)
        
        self.logger.error("MT5 bağlantısı başarısız, program sonlandırılıyor")
        return False
    
    def _setup_symbol(self) -> bool:
        """Symbol kurulumu ve kontrolü"""
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            self.logger.warning(f"Symbol {self.symbol} bulunamadı, alternatifler deneniyor...")
            
            alternatives = ["XAUUSD", "GOLD", "XAU/USD", "XAUUSD."]
            for alt_symbol in alternatives:
                alt_info = mt5.symbol_info(alt_symbol)
                if alt_info is not None:
                    self.logger.info(f"[OK] Alternatif symbol bulundu: {alt_symbol}")
                    self.symbol = alt_symbol
                    symbol_info = alt_info
                    break
            
            if symbol_info is None:
                self.logger.error("Hiçbir uygun symbol bulunamadı!")
                return False
        
        if not mt5.symbol_select(self.symbol, True):
            self.logger.error(f"Symbol seçilemedi: {self.symbol}")
            return False
        
        self.logger.info(f"[OK] Symbol kuruldu: {self.symbol}")
        
        test_rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 10)
        if test_rates is None or len(test_rates) == 0:
            self.logger.error(f"Test verisi alınamadı")
            return False
        
        self.logger.info(f"[OK] Test verisi başarılı: {len(test_rates)} bar")
        return True

    def get_data(self, bars=300) -> Optional[pd.DataFrame]:
        """Market verilerini al ve cache'le"""
        current_time = datetime.now()
        
        if self.data_cache is not None and self.last_data_time is not None:
            bar_duration = timedelta(minutes=15 if self.timeframe == mt5.TIMEFRAME_M15 else 5)
            if current_time - self.last_data_time < bar_duration:
                return self.data_cache
        
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            self.logger.error(f"Veri alınamadı")
            return None
        
        self.logger.debug(f"[OK] {len(rates)} bar alındı")
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        self.data_cache = df.copy()
        self.last_data_time = current_time
        
        return df

    def calculate_bollinger_bands(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Bollinger Bands hesapla"""
        close = df['close'].values
        if len(close) < self.bb_period:
            return np.zeros(len(close)), np.zeros(len(close)), np.zeros(len(close))
        
        bb_upper, bb_middle, bb_lower = talib.BBANDS(close, 
                                                    timeperiod=self.bb_period, 
                                                    nbdevup=self.bb_std, 
                                                    nbdevdn=self.bb_std)
        return bb_upper, bb_middle, bb_lower

    def calculate_macd(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """MACD hesapla"""
        close = df['close'].values
        if len(close) < self.macd_slow:
            return np.zeros(len(close)), np.zeros(len(close)), np.zeros(len(close))
        
        macd, macd_signal, macd_hist = talib.MACD(close, 
                                                 fastperiod=self.macd_fast,
                                                 slowperiod=self.macd_slow, 
                                                 signalperiod=self.macd_signal)
        return macd, macd_signal, macd_hist

    def analyze_trend_strength(self, df: pd.DataFrame) -> Dict:
        """Gelişmiş trend gücü analizi"""
        if len(df) < self.trend_confirmation_period:
            return {'direction': 'SIDEWAYS', 'strength': 0, 'consistency': 0}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # Trend yönü belirleme
        ma_short = talib.SMA(close, timeperiod=self.media1_period)
        ma_medium = talib.SMA(close, timeperiod=self.media2_period)
        ma_long = talib.SMA(close, timeperiod=self.media3_period)
        
        current_ma_short = ma_short[-1] if len(ma_short) > 0 and not np.isnan(ma_short[-1]) else close[-1]
        current_ma_medium = ma_medium[-1] if len(ma_medium) > 0 and not np.isnan(ma_medium[-1]) else close[-1]
        current_ma_long = ma_long[-1] if len(ma_long) > 0 and not np.isnan(ma_long[-1]) else close[-1]
        
        # Trend yönü
        if current_ma_short > current_ma_medium > current_ma_long:
            trend_direction = 'UPTREND'
        elif current_ma_short < current_ma_medium < current_ma_long:
            trend_direction = 'DOWNTREND'
        else:
            trend_direction = 'SIDEWAYS'
        
        # Trend tutarlılığı
        lookback = min(self.min_trend_bars, len(close))
        recent_closes = close[-lookback:]
        
        if len(recent_closes) < 2:
            return {'direction': 'SIDEWAYS', 'strength': 0, 'consistency': 0}
        
        higher_highs = 0
        higher_lows = 0
        lower_highs = 0
        lower_lows = 0
        
        for i in range(1, len(recent_closes)):
            if high[-lookback:][i] > high[-lookback:][i-1]:
                higher_highs += 1
            else:
                lower_highs += 1
            
            if low[-lookback:][i] > low[-lookback:][i-1]:
                higher_lows += 1
            else:
                lower_lows += 1
        
        # Trend gücü hesaplama
        if trend_direction == 'UPTREND':
            strength = (higher_highs + higher_lows) / (lookback * 2)
        elif trend_direction == 'DOWNTREND':
            strength = (lower_highs + lower_lows) / (lookback * 2)
        else:
            strength = 0
        
        consistency = abs(higher_highs - lower_highs) / lookback if lookback > 0 else 0
        
        return {
            'direction': trend_direction,
            'strength': strength,
            'consistency': consistency,
            'higher_highs': higher_highs,
            'higher_lows': higher_lows,
            'lower_highs': lower_highs,
            'lower_lows': lower_lows
        }

    def check_momentum_divergence(self, df: pd.DataFrame) -> Dict:
        """Momentum divergence kontrolü"""
        if len(df) < 50:
            return {'bullish_divergence': False, 'bearish_divergence': False}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        rsi = talib.RSI(close, timeperiod=self.rsi_period)
        macd, _, _ = self.calculate_macd(df)
        
        if len(rsi) < 20 or len(macd) < 20:
            return {'bullish_divergence': False, 'bearish_divergence': False}
        
        recent_high = np.max(high[-20:])
        recent_low = np.min(low[-20:])
        recent_high_idx = np.argmax(high[-20:]) + len(high) - 20
        recent_low_idx = np.argmin(low[-20:]) + len(low) - 20
        
        bullish_divergence = False
        bearish_divergence = False
        
        # Bullish divergence
        if (recent_low_idx > len(low) - 10 and  
            len(rsi) > recent_low_idx and
            len(macd) > recent_low_idx):
            
            price_trend = close[-1] - close[recent_low_idx]
            rsi_trend = rsi[-1] - rsi[recent_low_idx] if not np.isnan(rsi[recent_low_idx]) else 0
            macd_trend = macd[-1] - macd[recent_low_idx] if not np.isnan(macd[recent_low_idx]) else 0
            
            if price_trend < 0 and (rsi_trend > 0 or macd_trend > 0):
                bullish_divergence = True
        
        # Bearish divergence
        if (recent_high_idx > len(high) - 10 and  
            len(rsi) > recent_high_idx and
            len(macd) > recent_high_idx):
            
            price_trend = close[-1] - close[recent_high_idx]
            rsi_trend = rsi[-1] - rsi[recent_high_idx] if not np.isnan(rsi[recent_high_idx]) else 0
            macd_trend = macd[-1] - macd[recent_high_idx] if not np.isnan(macd[recent_high_idx]) else 0
            
            if price_trend > 0 and (rsi_trend < 0 or macd_trend < 0):
                bearish_divergence = True
        
        return {
            'bullish_divergence': bullish_divergence,
            'bearish_divergence': bearish_divergence
        }

    def analyze_price_action(self, df: pd.DataFrame) -> Dict:
        """Price action analizi"""
        if len(df) < 10:
            return {'bullish_pattern': False, 'bearish_pattern': False, 'strength': 0}
        
        open_prices = df['open'].values[-10:]
        high_prices = df['high'].values[-10:]
        low_prices = df['low'].values[-10:]
        close_prices = df['close'].values[-10:]
        
        if len(close_prices) < 3:
            return {'bullish_pattern': False, 'bearish_pattern': False, 'strength': 0}
        
        # Bullish patterns
        bullish_engulfing = (close_prices[-2] < open_prices[-2] and  
                           close_prices[-1] > open_prices[-1] and    
                           close_prices[-1] > open_prices[-2] and    
                           open_prices[-1] < close_prices[-2])       
        
        hammer = (close_prices[-1] > open_prices[-1] and  
                 (high_prices[-1] - max(close_prices[-1], open_prices[-1])) < 
                 (max(close_prices[-1], open_prices[-1]) - min(close_prices[-1], open_prices[-1])) * 0.1 and  
                 (min(close_prices[-1], open_prices[-1]) - low_prices[-1]) > 
                 (max(close_prices[-1], open_prices[-1]) - min(close_prices[-1], open_prices[-1])) * 2)  
        
        # Bearish patterns
        bearish_engulfing = (close_prices[-2] > open_prices[-2] and  
                           close_prices[-1] < open_prices[-1] and    
                           close_prices[-1] < open_prices[-2] and    
                           open_prices[-1] > close_prices[-2])       
        
        shooting_star = (close_prices[-1] < open_prices[-1] and  
                        (high_prices[-1] - max(close_prices[-1], open_prices[-1])) > 
                        (max(close_prices[-1], open_prices[-1]) - min(close_prices[-1], open_prices[-1])) * 2 and  
                        (min(close_prices[-1], open_prices[-1]) - low_prices[-1]) < 
                        (max(close_prices[-1], open_prices[-1]) - min(close_prices[-1], open_prices[-1])) * 0.1)  
        
        bullish_strength = 0
        bearish_strength = 0
        
        if bullish_engulfing:
            bullish_strength += 3
        if hammer:
            bullish_strength += 2
        if bearish_engulfing:
            bearish_strength += 3
        if shooting_star:
            bearish_strength += 2
        
        return {
            'bullish_pattern': bullish_engulfing or hammer,
            'bearish_pattern': bearish_engulfing or shooting_star,
            'bullish_strength': bullish_strength,
            'bearish_strength': bearish_strength
        }

    def check_multi_timeframe_confirmation(self, signal: str) -> bool:
        """Çoklu timeframe konfirmasyonu"""
        if not self.multi_timeframe_confirmation:
            return True
        
        try:
            higher_tf = self.timeframe * 4
            
            rates = mt5.copy_rates_from_pos(self.symbol, higher_tf, 0, 100)
            if rates is None or len(rates) < 50:
                return True
            
            htf_df = pd.DataFrame(rates)
            htf_df['time'] = pd.to_datetime(htf_df['time'], unit='s')
            
            htf_trend = self.analyze_trend_strength(htf_df)
            
            if signal in ["BUY", "STRONG_BUY"]:
                return htf_trend['direction'] in ['UPTREND'] and htf_trend['strength'] > 0.6  # Daha katı
            elif signal in ["SELL", "STRONG_SELL"]:
                return htf_trend['direction'] in ['DOWNTREND'] and htf_trend['strength'] > 0.6  # Daha katı
            
            return True
            
        except Exception as e:
            self.logger.debug(f"Multi-timeframe kontrolünde hata: {e}")
            return True

    def check_volatility_breakout(self, df: pd.DataFrame) -> bool:
        """Volatilite kırılım kontrolü"""
        if not self.volatility_breakout_filter or len(df) < 50:
            return True
        
        atr = self.get_atr(df)
        avg_atr = self.get_average_atr(20, df)
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df)
        
        current_price = df['close'].iloc[-1]
        
        atr_breakout = atr > avg_atr * 1.5  # Daha yüksek volatilite gerekli
        bb_squeeze = (bb_upper[-1] - bb_lower[-1]) < (bb_upper[-5] - bb_lower[-5])
        
        if not atr_breakout and bb_squeeze:
            self.logger.debug("Düşük volatilite dönemi - sinyal engellendi")
            return False
        
        return True

    def check_false_signal_history(self, signal: str) -> bool:
        """Geçmiş yanlış sinyal kontrolü"""
        current_time = datetime.now()
        
        # Ardışık kayıp kontrolü
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.logger.debug(f"Maksimum ardışık kayıp: {self.consecutive_losses}")
            return False
        
        self.recent_signals = [
            s for s in self.recent_signals 
            if (current_time - s['time']).total_seconds() < 86400
        ]
        
        for recent_signal in self.recent_signals:
            time_diff = (current_time - recent_signal['time']).total_seconds()
            if (time_diff < self.false_signal_cooldown and 
                recent_signal['signal'] == signal):
                self.logger.debug(f"Sinyal cooldown aktif: {signal}")
                return False
        
        signal_key = signal.replace("STRONG_", "")
        if signal_key in self.signal_success_rate:
            success_rate = self.signal_success_rate[signal_key]
            if success_rate < 0.5:  # %50'nin altındaysa sinyal verme
                self.logger.debug(f"Düşük başarı oranı: {signal_key} = {success_rate:.2%}")
                return False
        
        return True

    def is_market_suitable(self) -> bool:
        """Market koşullarının uygun olup olmadığını kontrol et"""
        try:
            # Spread kontrolü (çok katı)
            if self.enable_spread_filter:
                tick = mt5.symbol_info_tick(self.symbol)
                if tick is None:
                    return False
                
                spread_pips = (tick.ask - tick.bid) / (0.0001 if 'JPY' not in self.symbol else 0.01)
                if spread_pips > self.max_spread:
                    self.logger.debug(f"Spread çok yüksek: {spread_pips} pips")
                    return False
            else:
                tick = mt5.symbol_info_tick(self.symbol)
                if tick is None:
                    return False
            
            # Volatilite kontrolü
            df = self.get_data(100)
            if df is None or len(df) < self.volatility_lookback:
                return False
            
            atr = self.get_atr(df)
            avg_atr = self.get_average_atr(self.volatility_lookback, df)
            
            if atr < avg_atr * 0.5:  # Çok düşük volatilite
                self.logger.debug(f"Volatilite çok düşük")
                return False
            
            # Market saatleri
            now_utc = datetime.utcnow()
            current_hour = now_utc.hour
            current_weekday = now_utc.weekday()
            
            if current_weekday >= 5:
                self.logger.debug(f"Hafta sonu")
                return False
            
            if not (self.market_hours['start'] <= current_hour <= self.market_hours['end']):
                self.logger.debug(f"Market saatleri dışında")
                return False
            
            # Günlük kayıp limiti
            today = datetime.now().strftime('%Y-%m-%d')
            daily_pnl = self.performance_tracker.daily_pnl.get(today, 0)
            if daily_pnl < -self.max_daily_loss:
                self.logger.warning(f"Günlük kayıp limiti aşıldı: {daily_pnl}")
                return False
            
            # Toplam drawdown kontrolü
            metrics = self.performance_tracker.get_performance_metrics()
            if metrics['max_drawdown'] > self.max_drawdown_limit:
                self.logger.warning(f"Max drawdown limiti aşıldı")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Market uygunluk kontrolünde hata: {e}")
            return False

    def get_atr(self, df: pd.DataFrame = None) -> float:
        """ATR hesapla"""
        if df is None:
            df = self.get_data(50)
            if df is None:
                return 0.001
        
        if len(df) < self.atr_period:
            return 0.001
        
        atr = talib.ATR(df['high'].values, df['low'].values, 
                       df['close'].values, timeperiod=self.atr_period)
        return atr[-1] if len(atr) > 0 and not np.isnan(atr[-1]) else 0.001

    def get_average_atr(self, periods: int, df: pd.DataFrame = None) -> float:
        """Ortalama ATR hesapla"""
        if df is None:
            df = self.get_data(periods + self.atr_period)
            if df is None:
                return 0.001
        
        if len(df) < periods + self.atr_period:
            return 0.001
        
        atr_values = talib.ATR(df['high'].values, df['low'].values, 
                              df['close'].values, timeperiod=self.atr_period)
        
        valid_atr = atr_values[~np.isnan(atr_values)]
        if len(valid_atr) == 0:
            return 0.001
        
        return np.mean(valid_atr[-periods:]) if len(valid_atr) >= periods else np.mean(valid_atr)

    def adjust_parameters_by_volatility(self, df: pd.DataFrame):
        """Volatiliteye göre parametreleri ayarla"""
        if not self.adaptive_mode:
            return
        
        atr = self.get_atr(df)
        avg_atr = self.get_average_atr(self.volatility_lookback, df)
        
        if avg_atr == 0:
            return
        
        volatility_ratio = atr / avg_atr
        
        # Volatilite çok yüksekse daha da konservatif ol
        if volatility_ratio > 2.0:
            self.min_signal_strength = 12  # Çok yüksek
            self.atr_multiplier = 4.0
            self.logger.debug("Aşırı yüksek volatilite - Ultra konservatif")
        elif volatility_ratio > 1.5:
            self.min_signal_strength = 10
            self.atr_multiplier = 3.5
            self.logger.debug("Yüksek volatilite - Çok konservatif")
        elif volatility_ratio < 0.7:
            self.min_signal_strength = 7
            self.atr_multiplier = 2.5
            self.logger.debug("Düşük volatilite - Biraz esnek")
        else:
            self.min_signal_strength = 8
            self.atr_multiplier = 3.0

    def calculate_dema(self, data: pd.Series, period: int) -> pd.Series:
        """Double Exponential Moving Average hesapla"""
        ema1 = data.ewm(span=period).mean()
        ema2 = ema1.ewm(span=period).mean()
        return 2 * ema1 - ema2

    def calculate_supertrend(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """SuperTrend göstergesini hesapla"""
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

    def find_pivot_points(self, df: pd.DataFrame) -> Tuple[List[Tuple], List[Tuple]]:
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

    def calculate_support_resistance(self, pivot_highs: List[Tuple], 
                                   pivot_lows: List[Tuple], df: pd.DataFrame) -> List[Dict]:
        """Destek ve direnç seviyelerini hesapla"""
        all_pivots = [(idx, price, 'high') for idx, price in pivot_highs]
        all_pivots.extend([(idx, price, 'low') for idx, price in pivot_lows])
        all_pivots.sort(key=lambda x: x[0], reverse=True)
        
        pivot_prices = [p[1] for p in all_pivots[:self.max_num_pivot]]
        
        if not pivot_prices:
            return []
        
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

    def calculate_supply_demand_zones(self, df: pd.DataFrame) -> Tuple[List[Dict], List[Dict]]:
        """Arz ve talep bölgelerini hesapla"""
        if len(df) < 100:
            return [], []
        
        high = df['high'].values[-100:]
        low = df['low'].values[-100:]
        volume = df['tick_volume'].values[-100:]
        
        price_max = np.max(high)
        price_min = np.min(low)
        price_range = price_max - price_min
        
        if price_range == 0:
            return [], []
        
        division_size = price_range / self.resolution_div
        total_volume = np.sum(volume)
        threshold_volume = total_volume * self.supply_demand_threshold / 100
        
        supply_zones = []
        demand_zones = []
        
        # Supply zones
        current_level = price_max
        for _ in range(self.resolution_div):
            level_volume = sum(
                volume[j] for j in range(len(volume))
                if high[j] >= current_level - division_size and low[j] <= current_level
            )
            
            if level_volume >= threshold_volume:
                supply_zones.append({
                    'high': current_level,
                    'low': current_level - division_size,
                    'volume': level_volume,
                    'strength': level_volume / total_volume * 100
                })
                break
            current_level -= division_size
        
        # Demand zones
        current_level = price_min
        for _ in range(self.resolution_div):
            level_volume = sum(
                volume[j] for j in range(len(volume))
                if high[j] >= current_level and low[j] <= current_level + division_size
            )
            
            if level_volume >= threshold_volume:
                demand_zones.append({
                    'high': current_level + division_size,
                    'low': current_level,
                    'volume': level_volume,
                    'strength': level_volume / total_volume * 100
                })
                break
            current_level += division_size
        
        return supply_zones, demand_zones

    def generate_enhanced_signals(self, df: pd.DataFrame) -> Optional[Dict]:
        """[SEARCH] YENİ GELİŞTİRİLMİŞ SİNYAL ÜRETİCİ - YUKSEK DOĞRULUK"""
        required_bars = max(self.media3_period, self.rsi_period, self.atr_period, 100)
        if len(df) < required_bars:
            if self.debug_mode:
                self.logger.debug(f"[X] Yetersiz veri: {len(df)} bars, gerekli: {required_bars}")
            return None
        
        self.signal_attempts += 1
        
        # Debug: Her 50 denemede bir istatistik göster
        if self.debug_mode and self.signal_attempts % 50 == 0:
            self.logger.info(f"[SEARCH] Sinyal Arama İstatistikleri:")
            self.logger.info(f"  Toplam Deneme: {self.signal_attempts}")
            self.logger.info(f"  Son Sinyal: {self.last_signal if self.last_signal else 'YOK'}")
            self.logger.info(f"  Son Sinyal Zamanı: {self.last_signal_time if self.last_signal_time else 'YOK'}")
        
        self.adjust_parameters_by_volatility(df)
        
        close = df['close'].values
        current_price = close[-1]
        previous_price = close[-2] if len(close) > 1 else current_price
        current_time = df['time'].iloc[-1]
        
        # [SEARCH] 1. TREND GÜÇ ANALİZİ (ULTRA ESNEK)
        trend_analysis = self.analyze_trend_strength(df)
        # Trend gücü kontrolü artık daha esnek - %30'un altında olan trendler bile kabul
        if trend_analysis['strength'] < self.trend_strength_threshold:
            if self.debug_mode and self.signal_attempts % 30 == 0:
                self.logger.debug(f"[X] Trend cok zayif: {trend_analysis['strength']:.2f} < {self.trend_strength_threshold}")
                self.logger.debug(f"    Trend Yonu: {trend_analysis['direction']}")
            return None
        
        # [SEARCH] 2. VOLATİLİTE KIRIILIM (ESNEK)
        if self.volatility_breakout_filter and not self.check_volatility_breakout(df):
            if self.debug_mode:
                self.logger.debug("[X] Volatilite kiriilim yetersiz")
            return None
        
        # [SEARCH] 3. MOMENTUM DİVERGENCE
        divergence = self.check_momentum_divergence(df)
        
        # [SEARCH] 4. TEKNİK GÖSTERGELERİ HESAPLA
        dema1 = self.calculate_dema(df['close'], self.media1_period)
        dema2 = self.calculate_dema(df['close'], self.media2_period)
        dema3 = self.calculate_dema(df['close'], self.media3_period)
        trend, supertrend = self.calculate_supertrend(df)
        
        rsi = talib.RSI(close, timeperiod=self.rsi_period)
        current_rsi = rsi[-1] if len(rsi) > 0 and not np.isnan(rsi[-1]) else 50
        macd, macd_signal, macd_hist = self.calculate_macd(df)
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df)
        
        # [SEARCH] 5. PRICE ACTION
        price_action = self.analyze_price_action(df)
        
        # [SEARCH] 6. PIVOT VE S/R
        pivot_highs, pivot_lows = self.find_pivot_points(df)
        sr_levels = self.calculate_support_resistance(pivot_highs, pivot_lows, df)
        supply_zones, demand_zones = self.calculate_supply_demand_zones(df)
        
        # [TARGET] SİNYAL ÜRETİMİ - DAHA ESNEK
        signal = None
        signal_strength = 0
        confirmation_count = 0
        rejection_reasons = []  # Debug için red sebepleri
        
        # [OK] 1. SUPERTREND + TREND YÖN UYUMU (ESNEK)
        supertrend_signal = False
        if len(trend) > 1:  # Daha esnek koşul
            # SuperTrend değişimi
            if (trend[-1] == 1 and trend[-2] == -1 and 
                trend_analysis['direction'] in ['UPTREND', 'SIDEWAYS']):  # SIDEWAYS de kabul
                signal = "BUY"
                signal_strength += 3  # Daha düşük puan
                confirmation_count += 1
                supertrend_signal = True
                if self.debug_mode:
                    self.logger.debug("[OK] SuperTrend BUY + trend uyumu")
            elif (trend[-1] == -1 and trend[-2] == 1 and 
                  trend_analysis['direction'] in ['DOWNTREND', 'SIDEWAYS']):  # SIDEWAYS de kabul
                signal = "SELL" 
                signal_strength += 3  # Daha düşük puan
                confirmation_count += 1
                supertrend_signal = True
                if self.debug_mode:
                    self.logger.debug("[OK] SuperTrend SELL + trend uyumu")
        
        # SuperTrend sinyali yoksa çık
        if not supertrend_signal:
            rejection_reasons.append("SuperTrend sinyali yok")
            if self.debug_mode and self.signal_attempts % 10 == 0:
                self.logger.debug(f"[X] SuperTrend sinyali yok - Trend: {trend[-1] if len(trend) > 0 else 'N/A'}")
            return None
        
        # [OK] 2. MOVING AVERAGE SIRALAM (ULTRA ESNEK)
        ma_alignment = True  # Varsayılan olarak geçer
        if len(dema1) > 1 and len(dema2) > 1:
            ma1 = dema1.iloc[-1]
            ma2 = dema2.iloc[-1] 
            
            # Ultra esnek MA koşulları - sadece fiyat MA1'in üstünde/altında olması yeterli
            if (signal == "BUY" and current_price > ma1):
                signal_strength += 2
                confirmation_count += 1
                if self.debug_mode:
                    self.logger.debug("[OK] Fiyat MA1 ustunde - BUY uygun")
            elif (signal == "SELL" and current_price < ma1):
                signal_strength += 2
                confirmation_count += 1
                if self.debug_mode:
                    self.logger.debug("[OK] Fiyat MA1 altinda - SELL uygun")
            
            # MA sıralaması bonus puan (zorunlu değil)
            if (signal == "BUY" and ma1 > ma2):
                signal_strength += 1
                if self.debug_mode:
                    self.logger.debug("[OK] MA1 > MA2 bonus")
            elif (signal == "SELL" and ma1 < ma2):
                signal_strength += 1
                if self.debug_mode:
                    self.logger.debug("[OK] MA1 < MA2 bonus")
        
        # MA alignment artık zorunlu değil, sadece bonus
        
        # [OK] 3. RSI FİLTRE (ULTRA ESNEK) - Sadece çok ekstrem durumlar reddedilir
        rsi_extreme_check = True
        if signal == "BUY":
            if current_rsi > 85:  # Çok ekstrem overbought
                rejection_reasons.append(f"RSI ekstrem yuksek: {current_rsi:.1f}")
                if self.debug_mode:
                    self.logger.debug(f"[X] RSI ekstrem yuksek: {current_rsi:.1f}")
                return None
            else:
                signal_strength += 1  # RSI bonus (her durumda)
                confirmation_count += 1
                if self.debug_mode:
                    self.logger.debug(f"[OK] RSI BUY kabul: {current_rsi:.1f}")
        elif signal == "SELL":
            if current_rsi < 15:  # Çok ekstrem oversold
                rejection_reasons.append(f"RSI ekstrem dusuk: {current_rsi:.1f}")
                if self.debug_mode:
                    self.logger.debug(f"[X] RSI ekstrem dusuk: {current_rsi:.1f}")
                return None
            else:
                signal_strength += 1  # RSI bonus (her durumda)
                confirmation_count += 1
                if self.debug_mode:
                    self.logger.debug(f"[OK] RSI SELL kabul: {current_rsi:.1f}")
        
        # RSI ideal aralık bonus
        if 30 <= current_rsi <= 70:
            signal_strength += 1
            if self.debug_mode:
                self.logger.debug("[OK] RSI ideal aralik bonus")
        
        # [OK] 4. MACD KONFİRMASYONU (İSTEĞE BAĞLI)
        macd_ok = True  # Varsayılan olarak geçer
        if (len(macd) > 1 and len(macd_signal) > 1 and 
            not np.isnan(macd[-1]) and not np.isnan(macd_signal[-1])):
            
            if (signal == "BUY" and macd[-1] > macd_signal[-1]):  # Basit koşul
                signal_strength += 2
                confirmation_count += 1
                if self.debug_mode:
                    self.logger.debug("[OK] MACD BUY konfirmasyonu")
            elif (signal == "SELL" and macd[-1] < macd_signal[-1]):  # Basit koşul
                signal_strength += 2
                confirmation_count += 1
                if self.debug_mode:
                    self.logger.debug("[OK] MACD SELL konfirmasyonu")
            # MACD uyumsuzluk artık sinyal iptal etmiyor
        
        # [OK] 5. BOLLINGER BANDS (İSTEĞE BAĞLI)
        bb_position = 0.5  # Varsayılan orta
        if len(bb_upper) > 0 and len(bb_lower) > 0:
            bb_width = bb_upper[-1] - bb_lower[-1]
            bb_position = (current_price - bb_lower[-1]) / bb_width
            
            if signal == "BUY" and bb_position <= 0.4:  # Daha esnek %40
                signal_strength += 1
                confirmation_count += 1
                if self.debug_mode:
                    self.logger.debug("[OK] BB BUY pozisyonu uygun")
            elif signal == "SELL" and bb_position >= 0.6:  # Daha esnek %60
                signal_strength += 1
                confirmation_count += 1
                if self.debug_mode:
                    self.logger.debug("[OK] BB SELL pozisyonu uygun")
        
        # [OK] 6. PRICE ACTION KONFİRMASYONU (İSTEĞE BAĞLI)
        if self.price_action_confirmation:
            if signal == "BUY" and price_action['bullish_pattern']:
                signal_strength += price_action['bullish_strength']
                confirmation_count += 1
                if self.debug_mode:
                    self.logger.debug("[OK] Bullish price action")
            elif signal == "SELL" and price_action['bearish_pattern']:
                signal_strength += price_action['bearish_strength']
                confirmation_count += 1
                if self.debug_mode:
                    self.logger.debug("[OK] Bearish price action")
            
            # Güçlü ters pattern kontrolü (sadece çok güçlü olanlar iptal eder)
            if (signal == "BUY" and price_action['bearish_pattern'] and 
                price_action['bearish_strength'] >= 4):  # Daha yüksek eşik
                rejection_reasons.append("Cok guclu bearish pattern")
                if self.debug_mode:
                    self.logger.debug("[X] Cok guclu bearish pattern - BUY iptal")
                return None
            elif (signal == "SELL" and price_action['bullish_pattern'] and 
                  price_action['bullish_strength'] >= 4):  # Daha yüksek eşik
                rejection_reasons.append("Cok guclu bullish pattern")
                if self.debug_mode:
                    self.logger.debug("[X] Cok guclu bullish pattern - SELL iptal")
                return None
        
        # [OK] 7. MOMENTUM DİVERGENCE (BONUS)
        if divergence['bullish_divergence'] and signal == "BUY":
            signal_strength += 3
            confirmation_count += 1
            if self.debug_mode:
                self.logger.debug("[OK] Bullish divergence bonus")
        elif divergence['bearish_divergence'] and signal == "SELL":
            signal_strength += 3
            confirmation_count += 1
            if self.debug_mode:
                self.logger.debug("[OK] Bearish divergence bonus")
        # Ters divergence artık iptal etmiyor
        
        # [OK] 8. SUPPORT/RESISTANCE KIRIILIM (BONUS)
        strong_breakout = False
        atr = self.get_atr(df)
        price_move = abs(current_price - previous_price)
        
        if price_move > atr * 0.2:  # Daha düşük eşik
            for level in sr_levels[:3]:  # Daha fazla seviye
                level_price = level['level']
                if (signal == "BUY" and previous_price <= level_price < current_price and 
                    level['strength'] >= 2):  # Daha düşük güç
                    signal_strength += level['strength']
                    strong_breakout = True
                    if self.debug_mode:
                        self.logger.debug(f"[OK] Resistance kirilimi: {level_price:.2f}")
                elif (signal == "SELL" and previous_price >= level_price > current_price and 
                      level['strength'] >= 2):  # Daha düşük güç
                    signal_strength += level['strength']
                    strong_breakout = True
                    if self.debug_mode:
                        self.logger.debug(f"[OK] Support kirilimi: {level_price:.2f}")
        
        if strong_breakout:
            confirmation_count += 1
        
        # [OK] 9. HACİM KONFİRMASYONU (İSTEĞE BAĞLI)
        volume_ok = True  # Varsayılan geçer
        if len(df) >= 20:
            volume_sma = df['tick_volume'].rolling(20).mean()
            current_volume = df['tick_volume'].iloc[-1]
            avg_volume = volume_sma.iloc[-1]
            
            if current_volume > avg_volume * 1.3:  # Daha düşük eşik
                signal_strength += 1
                confirmation_count += 1
                volume_ok = True
                if self.debug_mode:
                    self.logger.debug(f"[OK] Hacim bonus: {current_volume:.0f} vs {avg_volume:.0f}")
            elif current_volume < avg_volume * 0.2:  # Çok düşük hacim iptal eder
                rejection_reasons.append("Cok dusuk hacim")
                if self.debug_mode:
                    self.logger.debug("[X] Cok dusuk hacim")
                return None
        
        # [SEARCH] ESNEK FİLTRELER
        
        # Minimum konfirmasyon kontrolü (ESNEK)
        if confirmation_count < self.min_confirmations:
            rejection_reasons.append(f"Yetersiz konfirmasyon: {confirmation_count}/{self.min_confirmations}")
            if self.debug_mode and self.signal_attempts % 5 == 0:
                self.logger.debug(f"[X] Yetersiz konfirmasyon: {confirmation_count}/{self.min_confirmations}")
            return None
        
        # Geçmiş sinyal kontrolü
        if not self.check_false_signal_history(signal):
            rejection_reasons.append("False signal history")
            return None
        
        # Çoklu timeframe kontrolü (KAPALI)
        if self.multi_timeframe_confirmation and not self.check_multi_timeframe_confirmation(signal):
            rejection_reasons.append("Yuksek timeframe uyumsuz")
            if self.debug_mode:
                self.logger.debug("[X] Yuksek timeframe uyumsuz")
            return None
        
        # Sinyal cooldown (DAHA KISA)
        if (self.last_signal_time is not None and 
            (current_time - self.last_signal_time).total_seconds() < self.false_signal_cooldown):
            cooldown_remaining = self.false_signal_cooldown - (current_time - self.last_signal_time).total_seconds()
            rejection_reasons.append(f"Cooldown aktif: {cooldown_remaining:.0f}s")
            if self.debug_mode and self.signal_attempts % 20 == 0:
                self.logger.debug(f"[X] Cooldown aktif: {cooldown_remaining:.0f}s kaldi")
            return None
        
        # [TARGET] FİNAL ONAY
        if (signal and signal_strength >= self.min_signal_strength and 
            confirmation_count >= self.min_confirmations):
            
            # Aşırı volatilite kontrolü (ESNEK)
            if atr > self.get_average_atr(30, df) * 5:  # Daha yüksek limit
                rejection_reasons.append("Asiri volatilite")
                if self.debug_mode:
                    self.logger.debug("[X] Asiri volatilite")
                return None
            
            # Son güçlendirme
            if strong_breakout and volume_ok:
                signal = f"STRONG_{signal}"
                signal_strength += 1
            
            # BAŞARILI SINYAL!
            self.logger.info(f"[TARGET] GUCLU SINYAL: {signal}")
            self.logger.info(f"   [CHART] Guc: {signal_strength}/{self.min_signal_strength}")
            self.logger.info(f"   [OK] Konfirmasyon: {confirmation_count}/{self.min_confirmations}")
            self.logger.info(f"   [UP] RSI: {current_rsi:.1f}, Trend: {trend_analysis['direction']}")
            self.logger.info(f"   [STRONG] Trend Gucu: {trend_analysis['strength']:.2f}")
            
            # Sinyali kaydet
            self.last_signal = signal
            self.last_signal_time = current_time
            self.recent_signals.append({
                'signal': signal,
                'time': current_time,
                'strength': signal_strength,
                'confirmations': confirmation_count
            })
            
            # Telegram bildirimi gönder
            signal_data_for_telegram = {
                'signal': signal,
                'strength': signal_strength,
                'confirmations': confirmation_count,
                'price': current_price,
                'rsi': current_rsi,
                'trend_analysis': trend_analysis,
                'divergence': divergence,
                'price_action': price_action,
                'ma1': dema1.iloc[-1],
                'ma2': dema2.iloc[-1],
                'ma3': dema3.iloc[-1],
                'supertrend': supertrend[-1],
                'trend': trend[-1],
                'macd': macd[-1] if len(macd) > 0 else 0,
                'macd_signal': macd_signal[-1] if len(macd_signal) > 0 else 0,
                'bb_position': bb_position,
                'sr_levels': sr_levels,
                'supply_zones': supply_zones,
                'demand_zones': demand_zones,
                'atr': atr,
                'volume_ratio': current_volume / avg_volume if len(df) >= 20 else 1.0
            }
            
            # Telegram sinyal bildirimi
            self.telegram.send_trade_signal(signal_data_for_telegram)
            
            return {
                'signal': signal,
                'strength': signal_strength,
                'confirmations': confirmation_count,
                'price': current_price,
                'rsi': current_rsi,
                'trend_analysis': trend_analysis,
                'divergence': divergence,
                'price_action': price_action,
                'ma1': dema1.iloc[-1],
                'ma2': dema2.iloc[-1],
                'ma3': dema3.iloc[-1],
                'supertrend': supertrend[-1],
                'trend': trend[-1],
                'macd': macd[-1] if len(macd) > 0 else 0,
                'macd_signal': macd_signal[-1] if len(macd_signal) > 0 else 0,
                'bb_position': bb_position,
                'sr_levels': sr_levels,
                'supply_zones': supply_zones,
                'demand_zones': demand_zones,
                'atr': atr,
                'volume_ratio': current_volume / avg_volume if len(df) >= 20 else 1.0
            }
        
        # Debug bilgisi (daha sık)
        if self.debug_mode and self.signal_attempts % 20 == 0:
            self.logger.debug(f"[X] Sinyal reddedildi: {signal if signal else 'YOK'}")
            self.logger.debug(f"   Guc: {signal_strength}/{self.min_signal_strength}")
            self.logger.debug(f"   Konfirmasyon: {confirmation_count}/{self.min_confirmations}")
            self.logger.debug(f"   RSI: {current_rsi:.1f}, Trend: {trend_analysis['direction']} ({trend_analysis['strength']:.2f})")
            if rejection_reasons:
                self.logger.debug(f"   Red Sebepleri: {', '.join(rejection_reasons[:3])}")
        
        return None

    def calculate_position_size(self, signal_data: Dict, stop_loss: float) -> float:
        """Gelişmiş position sizing"""
        try:
            account_info = mt5.account_info()
            if account_info is None:
                return self.initial_lot_size
            
            # Risk miktarını hesapla
            account_balance = account_info.balance
            risk_amount = account_balance * self.risk_per_trade
            
            # Stop distance'ı hesapla
            current_price = signal_data['price']
            stop_distance = abs(current_price - stop_loss)
            
            if stop_distance == 0:
                return self.initial_lot_size
            
            # Symbol bilgilerini al
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info is None:
                return self.initial_lot_size
            
            # Contract value hesapla
            if 'USD' in self.symbol:
                pip_value = symbol_info.trade_tick_value
            else:
                pip_value = symbol_info.trade_tick_value
            
            # Position size hesapla
            if pip_value > 0:
                position_size = risk_amount / (stop_distance / symbol_info.point * pip_value)
            else:
                position_size = self.initial_lot_size
            
            # Sinyal gücüne göre ayarlama (çok konservatif)
            strength_multiplier = min(signal_data['strength'] / 15.0, 1.2)  # Max %20 artış
            position_size *= strength_multiplier
            
            # Limitler içinde tut
            position_size = max(self.min_lot_size, min(self.max_lot_size, position_size))
            
            # Minimum step size'a yuvarla
            step_size = symbol_info.volume_step
            position_size = round(position_size / step_size) * step_size
            
            self.logger.debug(f"Position size: {position_size}, Risk: ${risk_amount:.2f}")
            
            return position_size
            
        except Exception as e:
            self.logger.error(f"Position size hesaplama hatası: {e}")
            return self.initial_lot_size

    def calculate_dynamic_stop_take_profit(self, signal_data: Dict) -> Tuple[Optional[float], Optional[float]]:
        """Dinamik stop-loss ve take-profit hesaplama"""
        current_price = signal_data['price']
        signal = signal_data['signal']
        atr = signal_data['atr']
        signal_strength = signal_data['strength']
        
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            return None, None
        
        # ATR bazlı stop-loss (çok geniş)
        stop_multiplier = 3.5  # Çok geniş stop
        if signal_strength >= 12:
            stop_multiplier = 3.0  # Güçlü sinyallerde biraz dar
        elif signal_strength <= 8:
            stop_multiplier = 4.0  # Zayıf sinyallerde çok geniş
        
        # Take-profit (konservatif)
        risk_reward_ratio = 2.5  # 1:2.5
        if signal_strength >= 12:
            risk_reward_ratio = 3.0  # Güçlü sinyallerde 1:3
        
        if signal in ["BUY", "STRONG_BUY"]:
            stop_loss = current_price - (stop_multiplier * atr)
            take_profit = current_price + (risk_reward_ratio * stop_multiplier * atr)
            
            # S/R seviyelerine göre ayarlama
            for level in signal_data['sr_levels']:
                if level['level'] < current_price and level['level'] > stop_loss:
                    stop_loss = level['level'] - (atr * 0.2)
                    break
            
            for level in signal_data['sr_levels']:
                if level['level'] > current_price:
                    potential_tp = level['level'] - (atr * 0.2)
                    if potential_tp > current_price + (atr * stop_multiplier * 1.5):
                        take_profit = min(take_profit, potential_tp)
                    break
                    
        elif signal in ["SELL", "STRONG_SELL"]:
            stop_loss = current_price + (stop_multiplier * atr)
            take_profit = current_price - (risk_reward_ratio * stop_multiplier * atr)
            
            for level in signal_data['sr_levels']:
                if level['level'] > current_price and level['level'] < stop_loss:
                    stop_loss = level['level'] + (atr * 0.2)
                    break
            
            for level in signal_data['sr_levels']:
                if level['level'] < current_price:
                    potential_tp = level['level'] + (atr * 0.2)
                    if potential_tp < current_price - (atr * stop_multiplier * 1.5):
                        take_profit = max(take_profit, potential_tp)
                    break
        else:
            return None, None
        
        # Minimum tick size'a yuvarla
        tick_size = symbol_info.point
        stop_loss = round(stop_loss / tick_size) * tick_size
        take_profit = round(take_profit / tick_size) * tick_size
        
        # Risk/Reward kontrolü
        risk = abs(stop_loss - current_price)
        reward = abs(take_profit - current_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        if rr_ratio < 2.0:  # Minimum 1:2 R/R
            self.logger.debug(f"R/R çok düşük: {rr_ratio:.2f}")
            return None, None
        
        self.logger.debug(f"SL: {stop_loss:.5f}, TP: {take_profit:.5f}, R:R: {rr_ratio:.2f}")
        
        return stop_loss, take_profit

    def check_margin_level(self) -> bool:
        """Marjin seviyesi kontrolü"""
        try:
            account_info = mt5.account_info()
            if account_info is None:
                return False
            
            margin_level = account_info.margin_level
            
            if margin_level == 0.0 and account_info.margin == 0.0:
                return True
            
            if margin_level < self.min_margin_level:
                self.logger.warning(f"Marjin seviyesi yetersiz: {margin_level}%")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Marjin kontrolünde hata: {e}")
            return False

    def count_positions(self, position_type: int) -> int:
        """Pozisyon sayısını say"""
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            if not positions:
                return 0
            
            count = sum(1 for pos in positions 
                       if pos.magic == self.magic_number and pos.type == position_type)
            return count
            
        except Exception as e:
            self.logger.error(f"Pozisyon sayma hatası: {e}")
            return 0

    def place_order(self, order_type: int, stop_loss: float, take_profit: float, 
                   lot_size: float) -> bool:
        """Emir ver"""
        try:
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info is None:
                return False
            
            if not symbol_info.visible:
                if not mt5.symbol_select(self.symbol, True):
                    return False
            
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                return False
            
            price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
            
            volume = max(symbol_info.volume_min, 
                        min(symbol_info.volume_max, lot_size))
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "sl": stop_loss,
                "tp": take_profit,
                "deviation": 30,  # Daha geniş deviation
                "magic": self.magic_number,
                "comment": "ImprovedMegaTrendBot_v2",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                error_msg = f"Emir başarısız: {result.retcode if result else 'None'}"
                if result and hasattr(result, 'comment'):
                    error_msg += f" - {result.comment}"
                self.logger.error(error_msg)
                return False
            
            # Trade kaydı
            trade_record = TradeRecord(
                entry_time=datetime.now(),
                entry_price=price,
                signal_type="BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL",
                lot_size=volume,
                position_ticket=result.order,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            self.performance_tracker.log_trade_entry(trade_record)
            
            self.logger.info(f"🎯 EMİR BAŞARILI: {result.order} - "
                           f"{'BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL'} "
                           f"- {volume} lot - Price: {price:.5f}")
            
            # Telegram pozisyon açılma bildirimi
            order_type_str = "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL"
            self.telegram.send_trade_opened(order_type_str, volume, price, stop_loss, take_profit, result.order)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Emir verme hatası: {e}")
            return False

    def close_positions(self, position_type: Optional[int] = None) -> bool:
        """Pozisyonları kapat"""
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            if not positions:
                return True
            
            for position in positions:
                if position.magic != self.magic_number:
                    continue
                
                if position_type is not None and position.type != position_type:
                    continue
                
                order_type = (mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY 
                             else mt5.ORDER_TYPE_BUY)
                
                tick = mt5.symbol_info_tick(self.symbol)
                if tick is None:
                    continue
                
                price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
                
                close_request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": self.symbol,
                    "volume": position.volume,
                    "type": order_type,
                    "position": position.ticket,
                    "price": price,
                    "deviation": 30,
                    "magic": self.magic_number,
                    "comment": "Close by ImprovedMegaTrendBot_v2",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                result = mt5.order_send(close_request)
                
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    self.performance_tracker.log_trade_exit(
                        position.ticket, 
                        datetime.now(), 
                        price, 
                        position.profit
                    )
                    
                    # Ardışık kayıp takibi
                    if position.profit < 0:
                        self.consecutive_losses += 1
                    else:
                        self.consecutive_losses = 0
                    
                    self.logger.info(f"Pozisyon kapatıldı: {position.ticket}, PnL: {position.profit:.2f}")
                    
                    # Telegram pozisyon kapanma bildirimi
                    self.telegram.send_trade_closed(position.ticket, position.profit, price)
                else:
                    self.logger.error(f"Pozisyon kapatılamadı: {result.comment}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Pozisyon kapatma hatası: {e}")
            return False

    def check_profit_and_close(self):
        """Karlı pozisyonları kontrol et ve kapat"""
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            if not positions:
                return
            
            for position in positions:
                if position.magic != self.magic_number:
                    continue
                
                profit = position.profit
                position_value = position.volume * 100000
                min_profit_threshold = position_value * 0.0005  # %0.05
                
                if profit >= min_profit_threshold:
                    order_type = (mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY 
                                 else mt5.ORDER_TYPE_BUY)
                    
                    tick = mt5.symbol_info_tick(self.symbol)
                    if tick is None:
                        continue
                    
                    price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
                    
                    close_request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": self.symbol,
                        "volume": position.volume,
                        "type": order_type,
                        "position": position.ticket,
                        "price": price,
                        "deviation": 30,
                        "magic": self.magic_number,
                        "comment": "Profit target reached",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    
                    result = mt5.order_send(close_request)
                    
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        self.performance_tracker.log_trade_exit(
                            position.ticket, 
                            datetime.now(), 
                            price, 
                            profit
                        )
                                            self.consecutive_losses = 0  # Kar ile kapatılan pozisyon
                    self.logger.info(f"Pozisyon {position.ticket} kâr ile kapatıldı: ${profit:.2f}")
                    
                    # Telegram pozisyon kapanma bildirimi
                    self.telegram.send_trade_closed(position.ticket, profit, price)
                    else:
                        self.logger.error(f"Kar realizasyonu başarısız: {result.comment}")
                        
        except Exception as e:
            self.logger.error(f"Kâr kontrolünde hata: {e}")

    def log_performance_summary(self):
        """Performans özetini logla"""
        try:
            metrics = self.performance_tracker.get_performance_metrics()
            account_info = mt5.account_info()
            
            if account_info:
                self.logger.info(
                    f"\n🏆 === PERFORMANS ÖZETİ ==="
                    f"\n💰 Hesap Bakiyesi: ${account_info.balance:.2f}"
                    f"\n💎 Özkaynak: ${account_info.equity:.2f}"
                    f"\n📊 Toplam İşlem: {metrics['total_trades']}"
                    f"\n🎯 Kazanma Oranı: {metrics['win_rate']:.2%}"
                    f"\n⚡ Kâr Faktörü: {metrics['profit_factor']:.2f}"
                    f"\n💵 Toplam PnL: ${metrics['total_pnl']:.2f}"
                    f"\n📉 Max Drawdown: ${metrics['max_drawdown']:.2f}"
                    f"\n🔥 Mevcut Seri: {metrics['current_streak']}"
                    f"\n❌ Ardışık Kayıp: {self.consecutive_losses}"
                    f"\n========================"
                )
                
        except Exception as e:
            self.logger.error(f"Performans özeti loglanamadı: {e}")

    def run_bot(self):
        """Bot ana döngüsü"""
        self.logger.info("[START] IMPROVED MEGATREND BOT V2.0 BASLATILDI")
        self.logger.info("[TARGET] ULTRA YUKSEK DOGRULUK MOD AKTIF")
        
        if not self.initialize_mt5():
            self.logger.error("[X] Bot baslatilamadi")
            return
        
        loop_count = 0
        
        try:
            while True:
                loop_count += 1
                
                # Her 200 döngüde bir performans özeti
                if loop_count % 200 == 0:
                    self.log_performance_summary()
                
                # Günlük Telegram özeti (günde bir kez)
                current_hour = datetime.now().hour
                if loop_count % 1000 == 0 and current_hour == 18:  # Akşam 6'da
                    try:
                        metrics = self.performance_tracker.get_performance_metrics()
                        account_info = mt5.account_info()
                        if account_info and self.telegram.enabled:
                            self.telegram.send_daily_summary(metrics, account_info)
                    except Exception as e:
                        self.logger.error(f"Telegram günlük özet hatası: {e}")
                
                # Market uygunluk kontrolü
                if not self.is_market_suitable():
                    time.sleep(60)  # 1 dakika bekle
                    continue
                
                # Açık pozisyonların kâr kontrolü
                self.check_profit_and_close()
                
                # Veri al
                df = self.get_data()
                if df is None:
                    time.sleep(30)
                    continue
                
                # Sinyal üret
                signal_data = self.generate_enhanced_signals(df)
                if signal_data is None:
                    time.sleep(10)
                    continue
                
                signal = signal_data['signal']
                strength = signal_data['strength']
                
                # Marjin kontrolü
                if not self.check_margin_level():
                    time.sleep(60)
                    continue
                
                # Pozisyon sayıları
                buy_count = self.count_positions(mt5.POSITION_TYPE_BUY)
                sell_count = self.count_positions(mt5.POSITION_TYPE_SELL)
                
                # Stop-loss ve take-profit hesapla
                stop_loss, take_profit = self.calculate_dynamic_stop_take_profit(signal_data)
                if stop_loss is None or take_profit is None:
                    time.sleep(10)
                    continue
                
                # Position size hesapla
                lot_size = self.calculate_position_size(signal_data, stop_loss)
                
                # BUY sinyali işleme
                if signal in ["BUY", "STRONG_BUY"] and buy_count < self.max_positions:
                    # Güçlü ters sinyal varsa pozisyonları kapat
                    if signal == "STRONG_BUY" and sell_count > 0:
                        self.close_positions(mt5.POSITION_TYPE_SELL)
                        self.logger.info("🔥 GÜÇLÜ BUY - SELL pozisyonları kapatıldı")
                        time.sleep(3)
                    
                    if self.place_order(mt5.ORDER_TYPE_BUY, stop_loss, take_profit, lot_size):
                        self.logger.info(f"✅ BUY EMRİ BAŞARILI - Güç: {strength}, "
                                       f"Lot: {lot_size}, SL: {stop_loss:.5f}, TP: {take_profit:.5f}")
                
                # SELL sinyali işleme
                elif signal in ["SELL", "STRONG_SELL"] and sell_count < self.max_positions:
                    if signal == "STRONG_SELL" and buy_count > 0:
                        self.close_positions(mt5.POSITION_TYPE_BUY)
                        self.logger.info("🔥 GÜÇLÜ SELL - BUY pozisyonları kapatıldı")
                        time.sleep(3)
                    
                    if self.place_order(mt5.ORDER_TYPE_SELL, stop_loss, take_profit, lot_size):
                        self.logger.info(f"✅ SELL EMRİ BAŞARILI - Güç: {strength}, "
                                       f"Lot: {lot_size}, SL: {stop_loss:.5f}, TP: {take_profit:.5f}")
                
                time.sleep(15)  # 15 saniye bekle
                
        except KeyboardInterrupt:
            self.logger.info("[STOP] Bot kullanici tarafindan durduruldu")
        except Exception as e:
            self.logger.error(f"[X] Bot ana dongusunde hata: {e}")
        finally:
            self.log_performance_summary()
            mt5.shutdown()
            self.logger.info("[WAVE] Bot kapatildi")

if __name__ == "__main__":
    # Windows terminal için güvenli çıktı
    def safe_print(text):
        try:
            print(text)
        except UnicodeEncodeError:
            # Emoji'leri güvenli karakterlerle değiştir
            emoji_map = {
                '🚀': '[START]', '🎯': '[TARGET]', '📊': '[CHART]', '⚡': '[POWER]',
                '💰': '[MONEY]', '📈': '[UP]', '🛡️': '[SHIELD]', '⏰': '[TIME]',
                '🔒': '[LOCK]'
            }
            for emoji, replacement in emoji_map.items():
                text = text.replace(emoji, replacement)
            print(text)
    
    safe_print("[START] IMPROVED MEGATREND BOT V2.0")
    safe_print("[TARGET] ULTRA YUKSEK DOGRULUK MOD")
    safe_print("=" * 50)
    
    # Telegram bilgileri
    TELEGRAM_BOT_TOKEN = "7594813856:AAGYoqUnHkT6Mybo7L3goS-Rw_7dJ8bnRpU"
    TELEGRAM_CHAT_ID = "6694433256"
    
    # Bot parametrelerini özelleştir (Telegram dahil)
    bot = ImprovedMegaTrendBot(
        symbol="XAUUSD+",
        timeframe=mt5.TIMEFRAME_M1,
        initial_lot_size=0.01,
        risk_per_trade=0.005,  # %0.5 risk (çok konservatif)
        enable_spread_filter=False,  # Spread kontrolü KAPALI
        telegram_token=TELEGRAM_BOT_TOKEN,
        telegram_chat_id=TELEGRAM_CHAT_ID
    )
    
    # Ultra esnek ayarlar - çok daha fazla sinyal
    bot.min_signal_strength = 3     # ULTRA DÜŞÜK (önceki: 5)
    bot.max_positions = 1           # Tek pozisyon (güvenli)
    bot.max_daily_loss = 50.0       # $50 günlük limit
    bot.false_signal_cooldown = 180 # 3 dakika (önceki: 5 dakika)
    bot.min_confirmations = 2       # 2 konfirmasyon (önceki: 3)
    bot.debug_mode = True           # Debug modu aktif
    
    # Bot başlangıç bildirimi
    if bot.telegram.enabled:
        bot.telegram.send_message("🚀 <b>IMPROVED MEGATREND BOT BAŞLATILDI</b> 🚀\n\n"
                                f"📊 Timeframe: {timeframe_names.get(bot.timeframe, 'M1')}\n"
                                f"⚡ Min Sinyal Gücü: {bot.min_signal_strength}\n"
                                f"🛡️ Min Konfirmasyon: {bot.min_confirmations}\n"
                                f"⏰ Cooldown: {bot.false_signal_cooldown}s")
    
    timeframe_names = {
        1: "M1", 5: "M5", 15: "M15", 30: "M30", 
        16385: "H1", 16388: "H4", 16408: "D1"
    }
    tf_name = timeframe_names.get(bot.timeframe, f"TF{bot.timeframe}")
    
    safe_print(f"[CHART] Timeframe: {tf_name}")
    safe_print(f"[POWER] Min Sinyal Gucu: {bot.min_signal_strength}")
    safe_print(f"[MONEY] Risk per trade: {bot.risk_per_trade*100}%")
    safe_print(f"[UP] Max pozisyonlar: {bot.max_positions}")
    safe_print(f"[SHIELD] Min konfirmasyon: {bot.min_confirmations}")
    safe_print(f"[TIME] Sinyal cooldown: {bot.false_signal_cooldown}s")
    safe_print(f"[LOCK] Spread kontrolu: {'ACIK' if bot.enable_spread_filter else 'KAPALI'}")
    safe_print("=" * 50)
    safe_print("[TARGET] Bot baslatiliyor...")
    
    bot.run_bot()