import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime, timedelta
import talib
import warnings
warnings.filterwarnings('ignore')

# Loglama yapılandırması: Hem dosyaya hem terminale yaz
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),  # Logları dosyaya yaz
        logging.StreamHandler()          # Logları terminale yaz
    ]
)

class MegaTrendBot:
    def __init__(self, symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M5, lot_size=0.01):
        self.symbol = symbol
        self.timeframe = timeframe
        self.lot_size = lot_size
        self.magic_number = 1234544
        self.max_positions = 3
        self.min_margin_level = 50.0
        self.min_signal_strength = 2
        self.media1_period = 20
        self.media2_period = 50
        self.media3_period = 200
        self.atr_period = 10
        self.atr_multiplier = 1.0
        self.pivot_period = 10
        self.max_num_pivot = 20
        self.channel_width = 10
        self.max_num_sr = 5
        self.min_strength = 2
        self.supply_demand_threshold = 10.0
        self.resolution_div = 50
        self.pivot_proximity_threshold = 0.002
        self.logger = logging.getLogger(__name__)
        self.last_signal = None
        self.last_signal_time = None
        self.support_levels = []
        self.resistance_levels = []
        self.supply_zones = []
        self.demand_zones = []
        self.last_data_time = None
        self.data_cache = None
        self.start_balance = None
        self.last_trade_time = None
        self.min_trade_interval = timedelta(minutes=15)  # 15 dakika bekleme
        self.daily_gain_limit = 10  # %10 kazanç
        self.daily_loss_limit = -5  # %5 kayıp
        self.initialize_mt5()

    def initialize_mt5(self):
        for attempt in range(3):
            if mt5.initialize():
                account_info = mt5.account_info()
                if account_info is not None:
                    self.logger.info(f"MT5 bağlantısı başarılı - Hesap: {account_info.login}, Bakiye: {account_info.balance}, Marjin: {account_info.margin}, Marjin Seviyesi: {account_info.margin_level}%")
                    if self.start_balance is None:
                        self.start_balance = account_info.balance
                    return True
                self.logger.error(f"Hesap bilgileri alınamadı, deneme {attempt + 1}/3")
                mt5.shutdown()
                time.sleep(2)
            else:
                self.logger.error(f"MT5 başlatılamadı, deneme {attempt + 1}/3")
                time.sleep(2)
        self.logger.error("MT5 bağlantısı başarısız, program sonlandırılıyor")
        return False

    def calculate_lot_size(self, stop_loss_pips, risk_percent=1):
        account_info = mt5.account_info()
        if account_info is None:
            return self.lot_size
        balance = account_info.balance
        risk_amount = balance * risk_percent / 100
        pip_value = 0.1  # XAUUSD için pip değeri (örnek, brokerına göre değişebilir)
        lot_size = risk_amount / (stop_loss_pips * pip_value)
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info:
            lot_size = max(symbol_info.volume_min, min(symbol_info.volume_max, lot_size))
        return round(lot_size, 2)

    def check_daily_target(self):
        account_info = mt5.account_info()
        if account_info is None:
            return False
        if self.start_balance is None:
            self.start_balance = account_info.balance
        gain = (account_info.balance - self.start_balance) / self.start_balance * 100
        if gain >= self.daily_gain_limit:
            self.logger.info("Günlük hedefe ulaşıldı, bot durduruluyor.")
            return True
        elif gain <= self.daily_loss_limit:
            self.logger.info("Günlük maksimum kayıp aşıldı, bot durduruluyor.")
            return True
        return False

    def can_trade(self):
        now = datetime.now()
        if self.last_trade_time is None:
            return True
        if now - self.last_trade_time >= self.min_trade_interval:
            return True
        self.logger.info(f"İşlem arası minimum bekleme süresi dolmadı. Kalan: {(self.min_trade_interval - (now - self.last_trade_time)).seconds // 60} dakika")
        return False

    def get_data(self):
        if self.data_cache is not None and self.last_data_time is not None and datetime.now() - self.last_data_time < timedelta(minutes=1):
            return self.data_cache

        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 1000)
        if rates is None or len(rates) == 0:
            self.logger.error(f"Veri alınamadı: {self.symbol} - {self.timeframe}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        self.last_data_time = datetime.now()
        self.data_cache = df
        return df

    def get_atr(self, period=10):
        if self.data_cache is None or len(self.data_cache) < period:
            return 0
        return talib.ATR(self.data_cache['high'], self.data_cache['low'], self.data_cache['close'], period)[-1]

    def get_pivots(self, df, period=10):
        if len(df) < period:
            return [], []
        high_pivots = []
        low_pivots = []
        for i in range(period, len(df)):
            if df['high'].iloc[i] == df['high'].iloc[i-1]:
                high_pivots.append(df['high'].iloc[i])
            if df['low'].iloc[i] == df['low'].iloc[i-1]:
                low_pivots.append(df['low'].iloc[i])
        return high_pivots, low_pivots

    def get_sr_levels(self, df, atr_period=10, num_levels=5):
        if len(df) < atr_period:
            return []
        levels = []
        for i in range(atr_period, len(df)):
            high_range = df['high'].iloc[i] - df['low'].iloc[i]
            atr = talib.ATR(df['high'], df['low'], df['close'], atr_period)[i]
            if high_range > atr * 2: # Basit bir SR seviyesi belirleme
                levels.append({'level': df['high'].iloc[i], 'type': 'resistance'})
            if high_range < atr * 2: # Basit bir SR seviyesi belirleme
                levels.append({'level': df['low'].iloc[i], 'type': 'support'})
        return levels[:num_levels]

    def get_supply_demand_zones(self, df, atr_period=10, num_zones=3):
        if len(df) < atr_period:
            return []
        zones = []
        for i in range(atr_period, len(df)):
            high_range = df['high'].iloc[i] - df['low'].iloc[i]
            atr = talib.ATR(df['high'], df['low'], df['close'], atr_period)[i]
            if high_range > atr * 1.5: # Basit bir S/D bölgesi belirleme
                zones.append({'level': df['high'].iloc[i], 'type': 'supply'})
            if high_range < atr * 1.5: # Basit bir S/D bölgesi belirleme
                zones.append({'level': df['low'].iloc[i], 'type': 'demand'})
        return zones[:num_zones]

    def generate_signals(self, df):
        if df is None or len(df) == 0:
            return None

        # Basit bir trend izleme
        if df['close'].iloc[-1] > df['close'].iloc[-2] and df['close'].iloc[-2] > df['close'].iloc[-3]:
            signal = "BUY"
            strength = 3
        elif df['close'].iloc[-1] < df['close'].iloc[-2] and df['close'].iloc[-2] < df['close'].iloc[-3]:
            signal = "SELL"
            strength = 3
        else:
            signal = "HOLD"
            strength = 1

        # Pivot noktaları ve SR seviyeleri
        high_pivots, low_pivots = self.get_pivots(df, self.pivot_period)
        sr_levels = self.get_sr_levels(df, self.atr_period, self.max_num_sr)
        supply_zones = self.get_supply_demand_zones(df, self.atr_period, self.max_num_pivot)
        demand_zones = self.get_supply_demand_zones(df, self.atr_period, self.max_num_pivot) # Demand zones are the same as supply zones for simplicity

        # Basit bir sinyal oluşturma
        if signal == "BUY":
            if len(sr_levels) > 0 and sr_levels[0]['level'] < df['close'].iloc[-1]:
                signal = "STRONG_BUY"
                strength = 4
            elif len(supply_zones) > 0 and supply_zones[0]['level'] < df['close'].iloc[-1]:
                signal = "BUY"
                strength = 2
        elif signal == "SELL":
            if len(sr_levels) > 0 and sr_levels[0]['level'] > df['close'].iloc[-1]:
                signal = "STRONG_SELL"
                strength = 4
            elif len(demand_zones) > 0 and demand_zones[0]['level'] > df['close'].iloc[-1]:
                signal = "SELL"
                strength = 2

        # SL ve TP hesaplama
        sl, tp, sl_pips = self.calculate_stop_loss_take_profit(df, signal)

        return {
            'signal': signal,
            'strength': strength,
            'sl': sl,
            'tp': tp,
            'sl_pips': sl_pips,
            'sr_levels': sr_levels,
            'supply_zones': supply_zones,
            'demand_zones': demand_zones
        }

    def calculate_stop_loss_take_profit(self, df, signal):
        current_price = df['close'].iloc[-1]
        atr = self.get_atr(self.atr_period)
        stop_loss_pips = 0
        if signal in ["BUY", "STRONG_BUY"]:
            stop_loss = current_price - (2 * atr)
            take_profit = current_price + (3 * atr)
            stop_loss_pips = (current_price - stop_loss) / 0.1  # pip değeri örnek
            for level in self.get_sr_levels(df, self.atr_period, self.max_num_sr):
                if level['level'] < current_price:
                    stop_loss = max(stop_loss, level['level'] - 0.0005)
                    stop_loss_pips = (current_price - stop_loss) / 0.1
                    break
        elif signal in ["SELL", "STRONG_SELL"]:
            stop_loss = current_price + (2 * atr)
            take_profit = current_price - (3 * atr)
            stop_loss_pips = (stop_loss - current_price) / 0.1
            for level in self.get_sr_levels(df, self.atr_period, self.max_num_sr):
                if level['level'] > current_price:
                    stop_loss = min(stop_loss, level['level'] + 0.0005)
                    stop_loss_pips = (stop_loss - current_price) / 0.1
                    break
        else:
            self.logger.debug("Geçersiz sinyal, SL/TP hesaplanamadı")
            return None, None, None
        self.logger.debug(f"SL: {stop_loss}, TP: {take_profit}, SL pip: {stop_loss_pips}")
        return stop_loss, take_profit, abs(stop_loss_pips)

    def place_order(self, order_type, sl, tp, lot_size):
        if mt5.order_send(
            symbol=self.symbol,
            type=order_type,
            action=mt5.TRADE_ACTION_DEAL,
            volume=lot_size,
            price=sl,
            sl=sl,
            tp=tp,
            magic=self.magic_number,
            comment="MegaTrendBot",
            type_time=mt5.ORDER_TIME_GTC,
            type_filling=mt5.ORDER_FILLING_FOK,
            type_expiration=0
        ) == -1:
            self.logger.error(f"Emri verme hatası: {mt5.last_error()}")
            return False
        self.logger.info(f"Emri verildi - Tip: {order_type}, Lot: {lot_size}, SL: {sl}, TP: {tp}")
        return True

    def close_positions(self, position_type):
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            self.logger.error(f"Pozisyonlar alınamadı: {mt5.last_error()}")
            return False
        for pos in positions:
            if pos.type == position_type:
                if mt5.order_send(
                    symbol=self.symbol,
                    type=mt5.ORDER_TYPE_SELL,
                    action=mt5.TRADE_ACTION_DEAL,
                    volume=pos.volume,
                    price=pos.price,
                    sl=pos.sl,
                    tp=pos.tp,
                    magic=self.magic_number,
                    comment="MegaTrendBot",
                    type_time=mt5.ORDER_TIME_GTC,
                    type_filling=mt5.ORDER_FILLING_FOK,
                    type_expiration=0
                ) == -1:
                    self.logger.error(f"Pozisyon kapatma hatası: {mt5.last_error()}")
                    return False
                self.logger.info(f"Pozisyon kapatıldı - Tip: {position_type}, Lot: {pos.volume}")
        return True

    def count_positions(self, position_type):
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            self.logger.error(f"Pozisyonlar alınamadı: {mt5.last_error()}")
            return 0
        count = 0
        for pos in positions:
            if pos.type == position_type:
                count += 1
        return count

    def check_margin_level(self):
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("Hesap bilgileri alınamadı.")
            return False
        if account_info.margin_level < self.min_margin_level:
            self.logger.warning(f"Marjin seviyesi yetersiz: {account_info.margin_level}% < {self.min_margin_level}%")
            return False
        return True

    def run_bot(self):
        self.logger.info("MegaTrend Bot başlatıldı...")
        if not self.initialize_mt5():
            self.logger.error("Bot başlatılamadı. Program sonlandırılıyor.")
            return
        while True:
            try:
                if self.check_daily_target():
                    self.logger.info("Günlük hedef/kayıp limiti nedeniyle bot durduruluyor.")
                    break
                df = self.get_data()
                if df is None:
                    self.logger.debug("Veri alınamadı, 5 saniye bekleniyor")
                    time.sleep(5)
                    continue
                signal_data = self.generate_signals(df)
                if signal_data is None:
                    self.logger.debug("Sinyal üretilmedi, 5 saniye bekleniyor")
                    time.sleep(5)
                    continue
                signal = signal_data['signal']
                strength = signal_data['strength']
                self.logger.debug(f"Sinyal: {signal}, Güç: {strength}")
                if strength < self.min_signal_strength:
                    self.logger.debug(f"Sinyal gücü yetersiz: {strength} < {self.min_signal_strength}")
                    time.sleep(5)
                    continue
                if not self.can_trade():
                    time.sleep(10)
                    continue
                if not self.check_margin_level():
                    self.logger.warning("Marjin seviyesi yetersiz. İşlem yapılmadı.")
                    time.sleep(10)
                    continue
                buy_count = self.count_positions(mt5.POSITION_TYPE_BUY)
                sell_count = self.count_positions(mt5.POSITION_TYPE_SELL)
                sl, tp, sl_pips = self.calculate_stop_loss_take_profit(df, signal)
                if sl is None or tp is None or sl_pips is None:
                    self.logger.debug("SL veya TP hesaplanamadı, işlem yapılmadı")
                    time.sleep(5)
                    continue
                lot_size = self.calculate_lot_size(sl_pips, risk_percent=1)
                if signal in ["BUY", "STRONG_BUY"] and buy_count < self.max_positions:
                    if sell_count > 0 and signal == "STRONG_BUY":
                        self.close_positions(mt5.POSITION_TYPE_SELL)
                        self.logger.info(f"Ters sinyal - SELL pozisyonları kapatıldı: {signal}")
                    if self.place_order(mt5.ORDER_TYPE_BUY, sl, tp, lot_size):
                        self.logger.info(f"BUY emri verildi - Güç: {strength}, SL: {sl}, TP: {tp}, Lot: {lot_size}")
                        self.last_trade_time = datetime.now()
                elif signal in ["SELL", "STRONG_SELL"] and sell_count < self.max_positions:
                    if buy_count > 0 and signal == "STRONG_SELL":
                        self.close_positions(mt5.POSITION_TYPE_BUY)
                        self.logger.info(f"Ters sinyal - BUY pozisyonları kapatıldı: {signal}")
                    if self.place_order(mt5.ORDER_TYPE_SELL, sl, tp, lot_size):
                        self.logger.info(f"SELL emri verildi - Güç: {strength}, SL: {sl}, TP: {tp}, Lot: {lot_size}")
                        self.last_trade_time = datetime.now()
                time.sleep(5)
            except KeyboardInterrupt:
                self.logger.info("Bot durduruldu...")
                break
            except Exception as e:
                self.logger.error(f"Hata oluştu: {str(e)}")
                time.sleep(10)
        mt5.shutdown()
        self.logger.info("Bot kapatıldı.")

if __name__ == "__main__":
    bot = MegaTrendBot()
    bot.run_bot()