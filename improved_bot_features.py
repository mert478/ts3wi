# MegaTrend Bot - Gelişmiş Özellikler ve İyileştirmeler

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

class EnhancedRiskManager:
    """Gelişmiş Risk Yönetimi Sınıfı"""
    
    def __init__(self, initial_balance: float, max_drawdown_percent: float = 20.0, 
                 daily_loss_limit_percent: float = 5.0):
        self.initial_balance = initial_balance
        self.max_drawdown_percent = max_drawdown_percent
        self.daily_loss_limit_percent = daily_loss_limit_percent
        self.daily_start_balance = initial_balance
        self.peak_balance = initial_balance
        
    def check_drawdown(self, current_equity: float) -> bool:
        """Maksimum drawdown kontrolü"""
        current_drawdown = (self.peak_balance - current_equity) / self.peak_balance * 100
        if current_drawdown > self.max_drawdown_percent:
            logging.warning(f"Maksimum drawdown aşıldı: {current_drawdown:.2f}%")
            return False
        
        # Peak balance güncelle
        if current_equity > self.peak_balance:
            self.peak_balance = current_equity
            
        return True
    
    def check_daily_loss_limit(self, current_equity: float) -> bool:
        """Günlük zarar limiti kontrolü"""
        daily_loss = (self.daily_start_balance - current_equity) / self.daily_start_balance * 100
        if daily_loss > self.daily_loss_limit_percent:
            logging.warning(f"Günlük zarar limiti aşıldı: {daily_loss:.2f}%")
            return False
        return True
    
    def reset_daily_balance(self, current_equity: float):
        """Günlük başlangıç bakiyesini sıfırla"""
        self.daily_start_balance = current_equity

class MarketConditionAnalyzer:
    """Market Koşulları Analiz Sınıfı"""
    
    @staticmethod
    def check_volatility_filter(df: pd.DataFrame, volatility_threshold: float = 2.0) -> bool:
        """Volatilite filtresi - Aşırı volatil piyasalarda işlem yapma"""
        atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values, 14)
        current_atr = atr[-1]
        avg_atr = np.mean(atr[-20:])
        
        if current_atr > avg_atr * volatility_threshold:
            logging.info(f"Yüksek volatilite tespit edildi. ATR: {current_atr:.5f}, Avg ATR: {avg_atr:.5f}")
            return False
        return True
    
    @staticmethod
    def is_trading_time() -> bool:
        """Major market saatleri kontrolü"""
        current_time = datetime.utcnow()
        hour = current_time.hour
        
        # London: 08:00-17:00 GMT, New York: 13:00-22:00 GMT
        london_session = 8 <= hour <= 17
        ny_session = 13 <= hour <= 22
        
        return london_session or ny_session
    
    @staticmethod
    def check_spread_filter(symbol: str, max_spread_points: int = 20) -> bool:
        """Spread filtresi - Yüksek spread durumunda işlem yapma"""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return False
        
        spread = tick.ask - tick.bid
        symbol_info = mt5.symbol_info(symbol)
        spread_points = spread / symbol_info.point
        
        if spread_points > max_spread_points:
            logging.info(f"Yüksek spread tespit edildi: {spread_points:.1f} points")
            return False
        return True

class TechnicalIndicators:
    """Ek Teknik İndikatörler"""
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> np.ndarray:
        """RSI hesaplama"""
        return talib.RSI(df['close'].values, timeperiod=period)
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """MACD hesaplama"""
        macd, macd_signal, macd_hist = talib.MACD(df['close'].values)
        return macd, macd_signal, macd_hist
    
    @staticmethod
    def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std: int = 2) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Bollinger Bands hesaplama"""
        upper, middle, lower = talib.BBANDS(df['close'].values, timeperiod=period, nbdevup=std, nbdevdn=std)
        return upper, middle, lower
    
    @staticmethod
    def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """Stochastic Oscillator hesaplama"""
        slowk, slowd = talib.STOCH(df['high'].values, df['low'].values, df['close'].values, 
                                   fastk_period=k_period, slowk_period=d_period, slowd_period=d_period)
        return slowk, slowd

class DatabaseManager:
    """Veritabanı Yönetim Sınıfı"""
    
    def __init__(self, db_path: str = "trading_bot.db"):
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
                duration_minutes INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE,
                balance REAL,
                equity REAL,
                margin REAL,
                free_margin REAL,
                margin_level REAL,
                daily_pnl REAL,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_trade(self, trade_data: Dict):
        """İşlem verisini kaydet"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (timestamp, symbol, signal_type, signal_strength, 
                              entry_price, stop_loss, take_profit, lot_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data['timestamp'], trade_data['symbol'], trade_data['signal_type'],
            trade_data['signal_strength'], trade_data['entry_price'], 
            trade_data['stop_loss'], trade_data['take_profit'], trade_data['lot_size']
        ))
        
        conn.commit()
        conn.close()
    
    def save_performance(self, perf_data: Dict):
        """Performans verisini kaydet"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO performance (date, balance, equity, margin, free_margin, 
                                   margin_level, daily_pnl, total_trades, 
                                   winning_trades, losing_trades)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            perf_data['date'], perf_data['balance'], perf_data['equity'],
            perf_data['margin'], perf_data['free_margin'], perf_data['margin_level'],
            perf_data['daily_pnl'], perf_data['total_trades'],
            perf_data['winning_trades'], perf_data['losing_trades']
        ))
        
        conn.commit()
        conn.close()

class PerformanceTracker:
    """Performans Takip Sınıfı"""
    
    def __init__(self):
        self.trades = []
        self.daily_stats = {}
        
    def add_trade(self, trade_result: Dict):
        """İşlem sonucunu ekle"""
        self.trades.append(trade_result)
        
    def calculate_metrics(self) -> Dict:
        """Performans metriklerini hesapla"""
        if not self.trades:
            return {}
        
        profits = [trade['profit'] for trade in self.trades]
        
        metrics = {
            'total_trades': len(self.trades),
            'winning_trades': len([p for p in profits if p > 0]),
            'losing_trades': len([p for p in profits if p < 0]),
            'win_rate': len([p for p in profits if p > 0]) / len(profits) * 100,
            'total_profit': sum(profits),
            'average_profit': np.mean(profits),
            'max_profit': max(profits),
            'max_loss': min(profits),
            'profit_factor': abs(sum([p for p in profits if p > 0])) / abs(sum([p for p in profits if p < 0])) if sum([p for p in profits if p < 0]) != 0 else 0
        }
        
        return metrics
    
    def calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        """Sharpe oranı hesapla"""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = np.array(returns) - risk_free_rate / 252
        return np.mean(excess_returns) / np.std(excess_returns) if np.std(excess_returns) != 0 else 0.0

class EnhancedSignalGenerator:
    """Gelişmiş Sinyal Üretici"""
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
    
    def generate_enhanced_signals(self, df: pd.DataFrame, original_signal: Dict) -> Dict:
        """Orijinal sinyali ek indikatörlerle güçlendir"""
        if original_signal is None:
            return None
        
        # RSI kontrolü
        rsi = self.indicators.calculate_rsi(df)
        current_rsi = rsi[-1]
        
        # MACD kontrolü
        macd, macd_signal, macd_hist = self.indicators.calculate_macd(df)
        
        # Bollinger Bands kontrolü
        bb_upper, bb_middle, bb_lower = self.indicators.calculate_bollinger_bands(df)
        current_price = df['close'].iloc[-1]
        
        # Stochastic kontrolü
        stoch_k, stoch_d = self.indicators.calculate_stochastic(df)
        
        signal_strength_bonus = 0
        
        # RSI confirmation
        if original_signal['signal'] in ['BUY', 'STRONG_BUY']:
            if current_rsi < 30:  # Oversold
                signal_strength_bonus += 2
            elif current_rsi < 50:
                signal_strength_bonus += 1
        elif original_signal['signal'] in ['SELL', 'STRONG_SELL']:
            if current_rsi > 70:  # Overbought
                signal_strength_bonus += 2
            elif current_rsi > 50:
                signal_strength_bonus += 1
        
        # MACD confirmation
        if len(macd) > 1 and len(macd_signal) > 1:
            if original_signal['signal'] in ['BUY', 'STRONG_BUY']:
                if macd[-1] > macd_signal[-1] and macd[-2] <= macd_signal[-2]:  # MACD crossover up
                    signal_strength_bonus += 2
            elif original_signal['signal'] in ['SELL', 'STRONG_SELL']:
                if macd[-1] < macd_signal[-1] and macd[-2] >= macd_signal[-2]:  # MACD crossover down
                    signal_strength_bonus += 2
        
        # Bollinger Bands confirmation
        if original_signal['signal'] in ['BUY', 'STRONG_BUY']:
            if current_price <= bb_lower[-1]:  # Price at lower band
                signal_strength_bonus += 1
        elif original_signal['signal'] in ['SELL', 'STRONG_SELL']:
            if current_price >= bb_upper[-1]:  # Price at upper band
                signal_strength_bonus += 1
        
        # Update signal strength
        original_signal['strength'] += signal_strength_bonus
        original_signal['rsi'] = current_rsi
        original_signal['macd_signal'] = macd[-1] > macd_signal[-1] if len(macd) > 0 else None
        original_signal['bb_position'] = 'upper' if current_price >= bb_upper[-1] else 'lower' if current_price <= bb_lower[-1] else 'middle'
        
        return original_signal

# Kullanım Örneği:
class EnhancedMegaTrendBot:
    """Geliştirilmiş MegaTrend Bot"""
    
    def __init__(self, symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M5, lot_size=0.01):
        # Orijinal parametreler
        self.symbol = symbol
        self.timeframe = timeframe
        self.lot_size = lot_size
        
        # Yeni bileşenler
        account_info = mt5.account_info()
        initial_balance = account_info.balance if account_info else 10000
        
        self.risk_manager = EnhancedRiskManager(initial_balance)
        self.market_analyzer = MarketConditionAnalyzer()
        self.db_manager = DatabaseManager()
        self.performance_tracker = PerformanceTracker()
        self.signal_generator = EnhancedSignalGenerator()
        
        self.logger = logging.getLogger(__name__)
    
    def enhanced_risk_check(self) -> bool:
        """Gelişmiş risk kontrolü"""
        account_info = mt5.account_info()
        if account_info is None:
            return False
        
        # Drawdown kontrolü
        if not self.risk_manager.check_drawdown(account_info.equity):
            return False
        
        # Günlük zarar limiti kontrolü
        if not self.risk_manager.check_daily_loss_limit(account_info.equity):
            return False
        
        # Spread kontrolü
        if not self.market_analyzer.check_spread_filter(self.symbol):
            return False
        
        return True
    
    def enhanced_market_filter(self, df: pd.DataFrame) -> bool:
        """Gelişmiş market filtresi"""
        # Trading saatleri kontrolü
        if not self.market_analyzer.is_trading_time():
            self.logger.info("Market saatleri dışında, işlem yapılmıyor")
            return False
        
        # Volatilite filtresi
        if not self.market_analyzer.check_volatility_filter(df):
            return False
        
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
            'lot_size': self.lot_size
        }
        self.db_manager.save_trade(trade_data)

# Örnek kullanım kodu:
if __name__ == "__main__":
    # Enhanced bot kullanımı
    enhanced_bot = EnhancedMegaTrendBot()
    
    # Performans metrikleri örneği
    print("Bot gelişmiş özelliklerle başlatıldı...")
    print("- Risk yönetimi aktif")
    print("- Market filtreleri aktif") 
    print("- Veritabanı kaydı aktif")
    print("- Performans takibi aktif")