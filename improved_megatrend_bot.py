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
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
warnings.filterwarnings('ignore')

# Gelişmiş loglama yapılandırması
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
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

class ImprovedMegaTrendBot:
    def __init__(self, symbol="XAUUSD+", timeframe=mt5.TIMEFRAME_M15, 
                 initial_lot_size=0.01, risk_per_trade=0.02, 
                 enable_spread_filter=True):
        # Temel parametreler
        self.symbol = symbol
        self.timeframe = timeframe
        self.initial_lot_size = initial_lot_size
        self.risk_per_trade = risk_per_trade
        self.enable_spread_filter = enable_spread_filter
        self.magic_number = 1234544
        
        # Risk yönetimi parametreleri
        self.max_positions = 3
        self.min_margin_level = 100.0  # %100
        self.max_spread = 1000.0  # 1000 pip (spread kontrolü devre dışı)
        self.max_lot_size = 1.0
        self.min_lot_size = 0.01
        self.max_daily_loss = 100.0  # $100 günlük kayıp limiti
        self.max_drawdown_limit = 500.0  # $500 toplam drawdown limiti
        
        # Teknik analiz parametreleri (daha düşük değerler)
        self.min_signal_strength = 2
        self.media1_period = 10
        self.media2_period = 20
        self.media3_period = 50
        self.atr_period = 10
        self.atr_multiplier = 2.0
        self.rsi_period = 14
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        
        # Pivot ve S/R parametreleri
        self.pivot_period = 10
        self.max_num_pivot = 20
        self.channel_width = 10
        self.max_num_sr = 5
        self.min_strength = 2
        self.supply_demand_threshold = 10.0
        self.resolution_div = 50
        self.pivot_proximity_threshold = 0.002
        
        # Adaptif parametreler
        self.adaptive_mode = True
        self.volatility_lookback = 20
        
        # Cache ve tracking
        self.data_cache = None
        self.last_data_time = None
        self.last_signal = None
        self.last_signal_time = None
        self.support_levels = []
        self.resistance_levels = []
        self.supply_zones = []
        self.demand_zones = []
        
        # Logger ve performance tracker
        self.logger = logging.getLogger(__name__)
        self.performance_tracker = PerformanceTracker()
        
        # Market filtresi (geçici olarak 24/7)
        self.market_hours = {
            'start': 0,   # GMT (24 saat)
            'end': 23     # GMT (24 saat)
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
                    
                    # Symbol seçimi ve kontrolü
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
        # İlk olarak mevcut symbol'ü dene
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            self.logger.warning(f"Symbol {self.symbol} bulunamadı, alternatifler deneniyor...")
            
            # Alternatif semboller
            alternatives = ["XAUUSD", "GOLD", "XAU/USD", "XAUUSD."]
            for alt_symbol in alternatives:
                alt_info = mt5.symbol_info(alt_symbol)
                if alt_info is not None:
                    self.logger.info(f"✅ Alternatif symbol bulundu: {alt_symbol}")
                    self.symbol = alt_symbol
                    symbol_info = alt_info
                    break
            
            if symbol_info is None:
                self.logger.error("Hiçbir uygun symbol bulunamadı!")
                return False
        
        # Symbol'ü seç
        if not mt5.symbol_select(self.symbol, True):
            self.logger.error(f"Symbol seçilemedi: {self.symbol}")
            return False
        
        self.logger.info(f"✅ Symbol kuruldu: {self.symbol}")
        self.logger.debug(f"   - Visible: {symbol_info.visible}")
        self.logger.debug(f"   - Point: {symbol_info.point}")
        self.logger.debug(f"   - Digits: {symbol_info.digits}")
        
        # Test verisi al
        test_rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 10)
        if test_rates is None or len(test_rates) == 0:
            self.logger.error(f"Test verisi alınamadı - Symbol: {self.symbol}, Timeframe: {self.timeframe}")
            return False
        
        self.logger.info(f"✅ Test verisi başarılı: {len(test_rates)} bar")
        return True

    def get_data(self, bars=200) -> Optional[pd.DataFrame]:
        """Market verilerini al ve cache'le"""
        current_time = datetime.now()
        
        # Cache kontrolü
        if self.data_cache is not None and self.last_data_time is not None:
            bar_duration = timedelta(minutes=15 if self.timeframe == mt5.TIMEFRAME_M15 else 5)
            if current_time - self.last_data_time < bar_duration:
                return self.data_cache
        
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
        if rates is None:
            self.logger.error(f"Veri alınamadı - Symbol: {self.symbol}, Timeframe: {self.timeframe}")
            return None
        elif len(rates) == 0:
            self.logger.error(f"Veri dizisi boş - Symbol: {self.symbol}")
            return None
        
        self.logger.debug(f"✅ {len(rates)} bar alındı - Symbol: {self.symbol}")
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Memory-efficient caching
        self.data_cache = df.copy()
        self.last_data_time = current_time
        
        return df

    def is_market_suitable(self) -> bool:
        """Market koşullarının uygun olup olmadığını kontrol et"""
        try:
            # Spread kontrolü (eğer aktifse)
            if self.enable_spread_filter:
                tick = mt5.symbol_info_tick(self.symbol)
                if tick is None:
                    return False
                
                spread_pips = (tick.ask - tick.bid) / (0.0001 if 'JPY' not in self.symbol else 0.01)
                if spread_pips > self.max_spread:
                    self.logger.debug(f"Spread çok yüksek: {spread_pips} pips")
                    return False
            else:
                # Spread kontrolü devre dışı - sadece tick kontrolü
                tick = mt5.symbol_info_tick(self.symbol)
                if tick is None:
                    return False
            
            # Volatilite kontrolü
            df = self.get_data(50)
            if df is None or len(df) < self.volatility_lookback:
                return False
            
            atr = self.get_atr(df)
            avg_atr = self.get_average_atr(self.volatility_lookback, df)
            
            if atr < avg_atr * 0.3:  # Çok düşük volatilite
                self.logger.debug(f"Volatilite çok düşük: ATR={atr}, Avg ATR={avg_atr}")
                return False
            
            # Market saatleri ve hafta sonu kontrolü
            now_utc = datetime.utcnow()
            current_hour = now_utc.hour
            current_weekday = now_utc.weekday()  # 0=Monday, 6=Sunday
            
            # Hafta sonu kontrolü (Cumartesi-Pazar)
            if current_weekday >= 5:  # 5=Saturday, 6=Sunday
                self.logger.debug(f"Hafta sonu, market kapalı: {current_weekday}")
                return False
            
            # Market saatleri kontrolü (Pazartesi 00:00 - Cuma 23:59 UTC)
            if not (self.market_hours['start'] <= current_hour <= self.market_hours['end']):
                self.logger.debug(f"Market saatleri dışında: {current_hour} UTC")
                return False
            
            # Günlük kayıp limiti kontrolü
            today = datetime.now().strftime('%Y-%m-%d')
            daily_pnl = self.performance_tracker.daily_pnl.get(today, 0)
            if daily_pnl < -self.max_daily_loss:
                self.logger.warning(f"Günlük kayıp limiti aşıldı: {daily_pnl}")
                return False
            
            # Toplam drawdown kontrolü
            metrics = self.performance_tracker.get_performance_metrics()
            if metrics['max_drawdown'] > self.max_drawdown_limit:
                self.logger.warning(f"Max drawdown limiti aşıldı: {metrics['max_drawdown']}")
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
        
        # Volatilite yüksekse daha konservatif ol
        if volatility_ratio > 1.5:
            self.min_signal_strength = 4
            self.atr_multiplier = 2.5
            self.logger.debug("Yüksek volatilite - Konservatif parametreler")
        elif volatility_ratio < 0.7:
            self.min_signal_strength = 2
            self.atr_multiplier = 1.5
            self.logger.debug("Düşük volatilite - Agresif parametreler")
        else:
            self.min_signal_strength = 3
            self.atr_multiplier = 2.0

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
            # Pivot high kontrolü
            is_pivot_high = all(high[j] < high[i] for j in range(i - self.pivot_period, i + self.pivot_period + 1) if j != i)
            if is_pivot_high:
                pivot_highs.append((i, high[i]))
            
            # Pivot low kontrolü
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
        
        # Supply zones (üst seviyeler)
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
        
        # Demand zones (alt seviyeler)
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
        """Gelişmiş sinyal üretimi"""
        required_bars = max(self.media3_period, self.rsi_period, self.atr_period)
        if len(df) < required_bars:
            self.logger.debug(f"Yetersiz veri: {len(df)} bars, gerekli: {required_bars}")
            return None
        
        # Volatiliteye göre parametreleri ayarla
        self.adjust_parameters_by_volatility(df)
        
        close = df['close'].values
        current_price = close[-1]
        previous_price = close[-2] if len(close) > 1 else current_price
        current_time = df['time'].iloc[-1]
        
        # Teknik göstergeleri hesapla
        dema1 = self.calculate_dema(df['close'], self.media1_period)
        dema2 = self.calculate_dema(df['close'], self.media2_period)
        dema3 = self.calculate_dema(df['close'], self.media3_period)
        trend, supertrend = self.calculate_supertrend(df)
        
        # RSI hesapla
        rsi = talib.RSI(close, timeperiod=self.rsi_period)
        current_rsi = rsi[-1] if len(rsi) > 0 and not np.isnan(rsi[-1]) else 50
        
        # Pivot noktaları ve S/R seviyeleri
        pivot_highs, pivot_lows = self.find_pivot_points(df)
        sr_levels = self.calculate_support_resistance(pivot_highs, pivot_lows, df)
        supply_zones, demand_zones = self.calculate_supply_demand_zones(df)
        
        signal = None
        signal_strength = 0
        
        # SuperTrend sinyali
        if len(trend) > 1:
            if trend[-1] == 1 and trend[-2] == -1:
                signal = "BUY"
                signal_strength += 3
                self.logger.debug(f"SuperTrend BUY sinyali: {current_price}")
            elif trend[-1] == -1 and trend[-2] == 1:
                signal = "SELL"
                signal_strength += 3
                self.logger.debug(f"SuperTrend SELL sinyali: {current_price}")
        
        # Moving Average sinyali
        if len(dema1) > 1 and len(dema2) > 1 and len(dema3) > 1:
            ma1_current = dema1.iloc[-1]
            ma2_current = dema2.iloc[-1]
            ma3_current = dema3.iloc[-1]
            
            if ma1_current > ma2_current > ma3_current and current_price > ma1_current:
                if signal == "BUY" or signal is None:
                    signal = "BUY"
                    signal_strength += 2
            elif ma1_current < ma2_current < ma3_current and current_price < ma1_current:
                if signal == "SELL" or signal is None:
                    signal = "SELL"
                    signal_strength += 2
        
        # RSI filtreleme
        if signal == "BUY" and current_rsi > self.rsi_overbought:
            signal_strength -= 2
            self.logger.debug(f"RSI overbought filtresi: {current_rsi}")
        elif signal == "SELL" and current_rsi < self.rsi_oversold:
            signal_strength -= 2
            self.logger.debug(f"RSI oversold filtresi: {current_rsi}")
        elif signal == "BUY" and current_rsi < self.rsi_oversold:
            signal_strength += 1  # Oversold'da BUY güçlendir
        elif signal == "SELL" and current_rsi > self.rsi_overbought:
            signal_strength += 1  # Overbought'ta SELL güçlendir
        
        # Support/Resistance kırılımları
        for level in sr_levels:
            level_price = level['level']
            if previous_price <= level_price < current_price and signal == "BUY":
                signal_strength += level['strength']
                self.logger.debug(f"Resistance kırıldı: {level_price}")
            elif previous_price >= level_price > current_price and signal == "SELL":
                signal_strength += level['strength']
                self.logger.debug(f"Support kırıldı: {level_price}")
        
        # Supply/Demand zone analizi
        for zone in supply_zones:
            if zone['low'] <= current_price <= zone['high'] and signal == "SELL":
                signal_strength += 1
        
        for zone in demand_zones:
            if zone['low'] <= current_price <= zone['high'] and signal == "BUY":
                signal_strength += 1
        
        # Pivot yakınlık kontrolü
        if len(pivot_highs) > 0:
            last_pivot_high = pivot_highs[-1][1]
            if abs(current_price - last_pivot_high) / current_price < self.pivot_proximity_threshold:
                if signal == "SELL" or signal is None:
                    signal = "STRONG_SELL"
                    signal_strength += 2
        
        if len(pivot_lows) > 0:
            last_pivot_low = pivot_lows[-1][1]
            if abs(current_price - last_pivot_low) / current_price < self.pivot_proximity_threshold:
                if signal == "BUY" or signal is None:
                    signal = "STRONG_BUY"
                    signal_strength += 2
        
        # Hacim konfirmasyonu
        if len(df) >= 20:
            volume_sma = df['tick_volume'].rolling(20).mean()
            current_volume = df['tick_volume'].iloc[-1]
            avg_volume = volume_sma.iloc[-1]
            
            if current_volume > avg_volume * 1.5:
                signal_strength += 1
                self.logger.debug(f"Yüksek hacim konfirmasyonu: {current_volume} vs {avg_volume}")
        
        # Aynı sinyal tekrarı kontrolü
        if (self.last_signal_time is not None and 
            self.last_signal == signal and 
            (current_time - self.last_signal_time).total_seconds() < 300):
            self.logger.debug(f"Aynı sinyal tekrarlandı: {signal}")
            return None
        
        # Sinyal gücü kontrolü
        if signal and signal_strength >= self.min_signal_strength:
            self.logger.info(f"Sinyal üretildi: {signal}, Güç: {signal_strength}, RSI: {current_rsi:.2f}")
            self.last_signal = signal
            self.last_signal_time = current_time
            
            return {
                'signal': signal,
                'strength': signal_strength,
                'price': current_price,
                'rsi': current_rsi,
                'ma1': dema1.iloc[-1],
                'ma2': dema2.iloc[-1],
                'ma3': dema3.iloc[-1],
                'supertrend': supertrend[-1],
                'trend': trend[-1],
                'sr_levels': sr_levels,
                'supply_zones': supply_zones,
                'demand_zones': demand_zones,
                'atr': self.get_atr(df)
            }
        
        self.logger.debug(f"Sinyal üretilmedi - Signal: {signal}, Güç: {signal_strength}")
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
                # Cross currency için
                pip_value = symbol_info.trade_tick_value
            
            # Position size hesapla
            if pip_value > 0:
                position_size = risk_amount / (stop_distance / symbol_info.point * pip_value)
            else:
                position_size = self.initial_lot_size
            
            # Sinyal gücüne göre ayarlama
            strength_multiplier = min(signal_data['strength'] / 5.0, 1.5)
            position_size *= strength_multiplier
            
            # Limitler içinde tut
            position_size = max(self.min_lot_size, min(self.max_lot_size, position_size))
            
            # Minimum step size'a yuvarla
            step_size = symbol_info.volume_step
            position_size = round(position_size / step_size) * step_size
            
            self.logger.debug(f"Position size hesaplandı: {position_size}, Risk: ${risk_amount:.2f}, "
                            f"Stop distance: {stop_distance:.5f}")
            
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
        
        # Symbol bilgilerini al
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            self.logger.error(f"Symbol bilgisi alınamadı: {self.symbol}")
            return None, None
        
        # ATR bazlı stop-loss
        stop_multiplier = 2.0
        if signal_strength >= 5:
            stop_multiplier = 1.5  # Güçlü sinyallerde daha dar stop
        elif signal_strength <= 2:
            stop_multiplier = 2.5  # Zayıf sinyallerde daha geniş stop
        
        # Take-profit risk/reward oranına göre
        risk_reward_ratio = 2.0  # 1:2 minimum
        if signal_strength >= 5:
            risk_reward_ratio = 3.0  # Güçlü sinyallerde 1:3
        
        if signal in ["BUY", "STRONG_BUY"]:
            stop_loss = current_price - (stop_multiplier * atr)
            take_profit = current_price + (risk_reward_ratio * stop_multiplier * atr)
            
            # Support/resistance seviyelerine göre ayarlama
            for level in signal_data['sr_levels']:
                if level['level'] < current_price and level['level'] > stop_loss:
                    stop_loss = level['level'] - (atr * 0.1)  # Biraz altına koy
                    break
            
            # Take profit'i resistance seviyesine ayarla
            for level in signal_data['sr_levels']:
                if level['level'] > current_price:
                    potential_tp = level['level'] - (atr * 0.1)
                    if potential_tp > current_price + (atr * stop_multiplier):  # Min R:R korunur
                        take_profit = min(take_profit, potential_tp)
                    break
                    
        elif signal in ["SELL", "STRONG_SELL"]:
            stop_loss = current_price + (stop_multiplier * atr)
            take_profit = current_price - (risk_reward_ratio * stop_multiplier * atr)
            
            # Resistance seviyelerine göre stop ayarlama
            for level in signal_data['sr_levels']:
                if level['level'] > current_price and level['level'] < stop_loss:
                    stop_loss = level['level'] + (atr * 0.1)
                    break
            
            # Take profit'i support seviyesine ayarla
            for level in signal_data['sr_levels']:
                if level['level'] < current_price:
                    potential_tp = level['level'] + (atr * 0.1)
                    if potential_tp < current_price - (atr * stop_multiplier):
                        take_profit = max(take_profit, potential_tp)
                    break
        else:
            return None, None
        
        # Minimum tick size'a yuvarla
        tick_size = symbol_info.point
        stop_loss = round(stop_loss / tick_size) * tick_size
        take_profit = round(take_profit / tick_size) * tick_size
        
        self.logger.debug(f"SL: {stop_loss:.5f}, TP: {take_profit:.5f}, "
                         f"R:R: {abs(take_profit - current_price) / abs(stop_loss - current_price):.2f}")
        
        return stop_loss, take_profit

    def check_margin_level(self) -> bool:
        """Marjin seviyesi kontrolü"""
        try:
            account_info = mt5.account_info()
            if account_info is None:
                self.logger.error("Hesap bilgileri alınamadı")
                return False
            
            margin_level = account_info.margin_level
            
            # Açık pozisyon yoksa marjin seviyesi 0 olabilir
            if margin_level == 0.0 and account_info.margin == 0.0:
                self.logger.debug("Açık pozisyon yok, marjin kontrolü geçildi")
                return True
            
            if margin_level < self.min_margin_level:
                self.logger.warning(f"Marjin seviyesi yetersiz: {margin_level}%")
                return False
            
            self.logger.debug(f"Marjin seviyesi uygun: {margin_level}%")
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
            
            # Volume kontrolü
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
                "deviation": 20,
                "magic": self.magic_number,
                "comment": "ImprovedMegaTrendBot",
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
            
            # Trade kaydını performance tracker'a ekle
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
            
            self.logger.info(f"Emir başarılı: {result.order} - "
                           f"{'BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL'} "
                           f"- {volume} lot - Price: {price:.5f}")
            return True
            
        except Exception as e:
            self.logger.error(f"Emir verme hatası: {e}")
            return False

    def close_positions(self, position_type: Optional[int] = None) -> bool:
        """Pozisyonları kapat"""
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            if not positions:
                self.logger.debug("Kapatılacak pozisyon yok")
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
                    "deviation": 20,
                    "magic": self.magic_number,
                    "comment": "Close by ImprovedMegaTrendBot",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                result = mt5.order_send(close_request)
                
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    # Performance tracker'a çıkış kaydı
                    self.performance_tracker.log_trade_exit(
                        position.ticket, 
                        datetime.now(), 
                        price, 
                        position.profit
                    )
                    self.logger.info(f"Pozisyon kapatıldı: {position.ticket}, PnL: {position.profit:.2f}")
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
                
                # Pozisyon değerinin %1'i kadar kâr varsa kapat (trailing profit)
                position_value = position.volume * 100000  # Standart lot değeri
                min_profit_threshold = position_value * 0.001  # %0.1
                
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
                        "deviation": 20,
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
                        self.logger.info(f"Pozisyon {position.ticket} kâr ile kapatıldı: ${profit:.2f}")
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
                    f"\n=== PERFORMANS ÖZETİ ==="
                    f"\nHesap Bakiyesi: ${account_info.balance:.2f}"
                    f"\nÖzkaynak: ${account_info.equity:.2f}"
                    f"\nToplam İşlem: {metrics['total_trades']}"
                    f"\nKazanma Oranı: {metrics['win_rate']:.2%}"
                    f"\nKâr Faktörü: {metrics['profit_factor']:.2f}"
                    f"\nToplam PnL: ${metrics['total_pnl']:.2f}"
                    f"\nMax Drawdown: ${metrics['max_drawdown']:.2f}"
                    f"\nMevcut Seri: {metrics['current_streak']}"
                    f"\n========================"
                )
                
        except Exception as e:
            self.logger.error(f"Performans özeti loglanamadı: {e}")

    def run_bot(self):
        """Bot ana döngüsü"""
        self.logger.info("Improved MegaTrend Bot başlatıldı...")
        
        if not self.initialize_mt5():
            self.logger.error("Bot başlatılamadı. Program sonlandırılıyor.")
            return
        
        loop_count = 0
        
        try:
            while True:
                loop_count += 1
                
                # Her 100 döngüde bir performans özeti
                if loop_count % 100 == 0:
                    self.log_performance_summary()
                
                # Market uygunluk kontrolü
                if not self.is_market_suitable():
                    self.logger.debug("Market koşulları uygun değil")
                    time.sleep(30)
                    continue
                
                # Açık pozisyonların kâr kontrolü
                self.check_profit_and_close()
                
                # Veri al
                df = self.get_data()
                if df is None:
                    self.logger.debug("Veri alınamadı, 10 saniye bekleniyor")
                    time.sleep(10)
                    continue
                
                # Sinyal üret
                signal_data = self.generate_enhanced_signals(df)
                if signal_data is None:
                    time.sleep(5)
                    continue
                
                signal = signal_data['signal']
                strength = signal_data['strength']
                
                # Marjin kontrolü
                if not self.check_margin_level():
                    self.logger.warning("Marjin seviyesi yetersiz")
                    time.sleep(30)
                    continue
                
                # Pozisyon sayıları
                buy_count = self.count_positions(mt5.POSITION_TYPE_BUY)
                sell_count = self.count_positions(mt5.POSITION_TYPE_SELL)
                
                # Stop-loss ve take-profit hesapla
                stop_loss, take_profit = self.calculate_dynamic_stop_take_profit(signal_data)
                if stop_loss is None or take_profit is None:
                    self.logger.debug("SL/TP hesaplanamadı")
                    time.sleep(5)
                    continue
                
                # Position size hesapla
                lot_size = self.calculate_position_size(signal_data, stop_loss)
                
                # BUY sinyali işleme
                if signal in ["BUY", "STRONG_BUY"] and buy_count < self.max_positions:
                    # Güçlü ters sinyal varsa mevcut pozisyonları kapat
                    if signal == "STRONG_BUY" and sell_count > 0:
                        self.close_positions(mt5.POSITION_TYPE_SELL)
                        self.logger.info("Güçlü BUY sinyali - SELL pozisyonları kapatıldı")
                        time.sleep(2)  # Kapatma işleminin tamamlanması için bekle
                    
                    if self.place_order(mt5.ORDER_TYPE_BUY, stop_loss, take_profit, lot_size):
                        self.logger.info(f"BUY emri başarılı - Güç: {strength}, "
                                       f"Lot: {lot_size}, SL: {stop_loss:.5f}, TP: {take_profit:.5f}")
                
                # SELL sinyali işleme
                elif signal in ["SELL", "STRONG_SELL"] and sell_count < self.max_positions:
                    # Güçlü ters sinyal varsa mevcut pozisyonları kapat
                    if signal == "STRONG_SELL" and buy_count > 0:
                        self.close_positions(mt5.POSITION_TYPE_BUY)
                        self.logger.info("Güçlü SELL sinyali - BUY pozisyonları kapatıldı")
                        time.sleep(2)
                    
                    if self.place_order(mt5.ORDER_TYPE_SELL, stop_loss, take_profit, lot_size):
                        self.logger.info(f"SELL emri başarılı - Güç: {strength}, "
                                       f"Lot: {lot_size}, SL: {stop_loss:.5f}, TP: {take_profit:.5f}")
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            self.logger.info("Bot kullanıcı tarafından durduruldu...")
        except Exception as e:
            self.logger.error(f"Bot ana döngüsünde hata: {e}")
        finally:
            # Son performans özeti
            self.log_performance_summary()
            # Tüm pozisyonları kapat (isteğe bağlı)
            # self.close_positions()
            mt5.shutdown()
            self.logger.info("Bot kapatıldı.")

if __name__ == "__main__":
    # Bot parametrelerini özelleştir
    bot = ImprovedMegaTrendBot(
        symbol="XAUUSD+",
        timeframe=mt5.TIMEFRAME_M15,
        initial_lot_size=0.01,
        risk_per_trade=0.02,  # Hesap bakiyesinin %2'si risk
        enable_spread_filter=False  # Spread kontrolünü devre dışı bırak
    )
    
    bot.run_bot()