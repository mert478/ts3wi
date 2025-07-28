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
    level=logging.INFO,  # DEBUG'dan INFO'ya değiştir (daha az log)
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scalping_bot.log'),
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
    
    def __init__(self, data_file="scalping_performance.json"):
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

class UltraScalpingBot:
    def __init__(self, symbol="XAUUSD+", timeframe=mt5.TIMEFRAME_M1, 
                 initial_lot_size=0.01, risk_per_trade=0.001):
        
        self.symbol = symbol
        self.timeframe = timeframe
        self.initial_lot_size = initial_lot_size
        self.risk_per_trade = risk_per_trade
        self.magic_number = 1234567
        
        # 🚀 ULTRA AGRESIF AYARLAR
        self.max_positions = 10          # Çok fazla pozisyon
        self.min_margin_level = 50.0     # Düşük margin req
        self.max_daily_loss = 30.0       # Küçük günlük limit
        self.max_lot_size = 0.1
        self.min_lot_size = 0.01
        
        # ⚡ ÇOK HIZLI TEKNİK GÖSTERGELER
        self.fast_ma = 3                 # Çok hızlı MA
        self.slow_ma = 7                 # Yine hızlı
        self.rsi_period = 5              # Çok kısa RSI
        self.atr_period = 3              # Çok kısa ATR
        
        # 🎯 BASIT SİNYAL KOŞULLARI
        self.min_price_move = 0.00005    # 0.5 pip hareket yeter
        self.signal_cooldown = 15        # 15 saniye bekleme
        self.volume_threshold = 0        # Volume kontrolü yok
        
        # 💰 DAR STOP/TAKE PROFIT
        self.stop_pips = 5               # 5 pip stop
        self.take_pips = 3               # 3 pip take (1:0.6 R:R)
        
        # Cache
        self.last_signal_time = None
        self.last_price = 0
        self.trade_count = 0
        
        self.logger = logging.getLogger(__name__)
        self.performance_tracker = PerformanceTracker()
        
        self.initialize_mt5()

    def initialize_mt5(self) -> bool:
        """MT5 başlat"""
        for attempt in range(3):
            if mt5.initialize():
                account_info = mt5.account_info()
                if account_info is not None:
                    self.logger.info(f"✅ MT5 bağlandı - Bakiye: ${account_info.balance:.2f}")
                    if self._setup_symbol():
                        return True
                mt5.shutdown()
                time.sleep(1)
        return False
    
    def _setup_symbol(self) -> bool:
        """Symbol kurulumu"""
        alternatives = [self.symbol, "XAUUSD", "GOLD", "XAU/USD"]
        
        for symbol in alternatives:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is not None:
                if mt5.symbol_select(symbol, True):
                    self.symbol = symbol
                    self.logger.info(f"✅ Symbol: {symbol}")
                    return True
        return False

    def get_data(self, bars=50) -> Optional[pd.DataFrame]:
        """Hızlı veri alma"""
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def ultra_simple_signal(self, df: pd.DataFrame) -> Optional[Dict]:
        """ULTRA BASİT SİNYAL - Sadece fiyat hareketi"""
        if len(df) < 10:
            return None
        
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        
        # Fiyat değişimi
        price_change = current_price - prev_price
        price_change_pct = abs(price_change / prev_price)
        
        # Cooldown kontrolü
        now = datetime.now()
        if (self.last_signal_time and 
            (now - self.last_signal_time).total_seconds() < self.signal_cooldown):
            return None
        
        signal = None
        strength = 1
        
        # ÇOK BASİT LOGİK: Fiyat yükseliyorsa BUY, düşüyorsa SELL
        if price_change > self.min_price_move:
            signal = "BUY"
            strength = 2 if price_change_pct > 0.0001 else 1
        elif price_change < -self.min_price_move:
            signal = "SELL"  
            strength = 2 if price_change_pct > 0.0001 else 1
        
        # Hızlı MA ile konfirmasyon
        if len(df) >= self.slow_ma:
            fast_ma = df['close'].rolling(self.fast_ma).mean().iloc[-1]
            slow_ma = df['close'].rolling(self.slow_ma).mean().iloc[-1]
            
            if signal == "BUY" and fast_ma > slow_ma:
                strength += 1
            elif signal == "SELL" and fast_ma < slow_ma:
                strength += 1
        
        if signal:
            self.last_signal_time = now
            self.logger.info(f"🎯 {signal} sinyali - Güç: {strength}, Fiyat: {current_price:.5f}")
            
            return {
                'signal': signal,
                'strength': strength,
                'price': current_price,
                'price_change': price_change
            }
        
        return None

    def calculate_simple_stop_take(self, signal: str, entry_price: float) -> Tuple[float, float]:
        """Basit sabit pip stop/take"""
        symbol_info = mt5.symbol_info(self.symbol)
        pip_size = 0.0001 if 'JPY' not in self.symbol else 0.01
        
        if signal == "BUY":
            stop_loss = entry_price - (self.stop_pips * pip_size)
            take_profit = entry_price + (self.take_pips * pip_size)
        else:  # SELL
            stop_loss = entry_price + (self.stop_pips * pip_size)
            take_profit = entry_price - (self.take_pips * pip_size)
        
        # Tick size'a yuvarla
        if symbol_info:
            tick = symbol_info.point
            stop_loss = round(stop_loss / tick) * tick
            take_profit = round(take_profit / tick) * tick
        
        return stop_loss, take_profit

    def place_trade(self, signal: str, entry_price: float) -> bool:
        """Hızlı trade açma"""
        try:
            order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
            stop_loss, take_profit = self.calculate_simple_stop_take(signal, entry_price)
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": self.initial_lot_size,
                "type": order_type,
                "price": entry_price,
                "sl": stop_loss,
                "tp": take_profit,
                "deviation": 30,
                "magic": self.magic_number,
                "comment": "UltraScalping",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.trade_count += 1
                
                # Performance tracking
                trade_record = TradeRecord(
                    entry_time=datetime.now(),
                    entry_price=entry_price,
                    signal_type=signal,
                    lot_size=self.initial_lot_size,
                    position_ticket=result.order,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                )
                self.performance_tracker.log_trade_entry(trade_record)
                
                self.logger.info(f"✅ Trade #{self.trade_count}: {signal} @ {entry_price:.5f} "
                               f"SL:{stop_loss:.5f} TP:{take_profit:.5f}")
                return True
            else:
                error = result.comment if result else "Bilinmeyen hata"
                self.logger.error(f"❌ Trade başarısız: {error}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Trade hatası: {e}")
            return False

    def count_open_positions(self) -> int:
        """Açık pozisyon sayısı"""
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return 0
        return len([p for p in positions if p.magic == self.magic_number])

    def check_basic_conditions(self) -> bool:
        """Temel koşul kontrolü"""
        # Account kontrol
        account = mt5.account_info()
        if not account:
            return False
        
        # Günlük kayıp kontrolü
        today = datetime.now().strftime('%Y-%m-%d')
        daily_pnl = self.performance_tracker.daily_pnl.get(today, 0)
        if daily_pnl < -self.max_daily_loss:
            return False
        
        # Pozisyon limit
        if self.count_open_positions() >= self.max_positions:
            return False
        
        # Tick kontrol
        tick = mt5.symbol_info_tick(self.symbol)
        return tick is not None

    def log_performance_summary(self):
        """Performans özeti"""
        metrics = self.performance_tracker.get_performance_metrics()
        account = mt5.account_info()
        
        if account:
            self.logger.info(
                f"\n📊 SCALPING ÖZET:"
                f"\n💰 Bakiye: ${account.balance:.2f}"
                f"\n📈 İşlem: {metrics['total_trades']}"
                f"\n🎯 Kazanma: {metrics['win_rate']:.1%}"
                f"\n💵 PnL: ${metrics['total_pnl']:.2f}"
                f"\n📉 Drawdown: ${metrics['max_drawdown']:.2f}"
            )

    def run_scalping_bot(self):
        """Ana scalping döngüsü"""
        self.logger.info("🚀 ULTRA SCALPING BOT BAŞLADI!")
        
        if not self.initialize_mt5():
            self.logger.error("❌ MT5 başlatılamadı!")
            return
        
        loop_count = 0
        
        try:
            while True:
                loop_count += 1
                
                # Her 200 döngüde performans
                if loop_count % 200 == 0:
                    self.log_performance_summary()
                
                # Temel kontroller
                if not self.check_basic_conditions():
                    time.sleep(5)
                    continue
                
                # Veri al
                df = self.get_data(20)  # Çok az veri
                if df is None:
                    time.sleep(2)
                    continue
                
                # Sinyal üret
                signal_data = self.ultra_simple_signal(df)
                if signal_data is None:
                    time.sleep(1)  # Çok hızlı döngü
                    continue
                
                # Trade aç
                signal = signal_data['signal']
                price = signal_data['price']
                
                if self.place_trade(signal, price):
                    self.logger.info(f"⚡ TRADE AÇILDI: {signal} @ {price:.5f}")
                    time.sleep(2)  # Trade sonrası kısa bekle
                else:
                    time.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Bot durduruldu!")
        except Exception as e:
            self.logger.error(f"❌ Beklenmeyen hata: {e}")
        finally:
            self.log_performance_summary()
            mt5.shutdown()
            self.logger.info("👋 Bot kapatıldı.")

if __name__ == "__main__":
    # 🚀 ULTRA SCALPING AYARLARI
    bot = UltraScalpingBot(
        symbol="XAUUSD+",
        timeframe=mt5.TIMEFRAME_M1,
        initial_lot_size=0.01,
        risk_per_trade=0.001
    )
    
    print("🔥 ULTRA SCALPING BOT - ÇOK SIK TİCARET MODU")
    print(f"⚡ Max pozisyon: {bot.max_positions}")
    print(f"⚡ Sinyal cooldown: {bot.signal_cooldown}s")
    print(f"⚡ Stop: {bot.stop_pips} pip, Take: {bot.take_pips} pip")
    print(f"⚡ Min hareket: {bot.min_price_move}")
    print("🎯 Her küçük fiyat hareketinde trade açacak!")
    
    bot.run_scalping_bot()