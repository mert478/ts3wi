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
        self.initialize_mt5()

    def initialize_mt5(self):
        for attempt in range(3):
            if mt5.initialize():
                account_info = mt5.account_info()
                if account_info is not None:
                    self.logger.info(f"MT5 bağlantısı başarılı - Hesap: {account_info.login}, Bakiye: {account_info.balance}, Marjin: {account_info.margin}, Marjin Seviyesi: {account_info.margin_level}%")
                    return True
                self.logger.error(f"Hesap bilgileri alınamadı, deneme {attempt + 1}/3")
                mt5.shutdown()
                time.sleep(2)
            else:
                self.logger.error(f"MT5 başlatılamadı, deneme {attempt + 1}/3")
                time.sleep(2)
        self.logger.error("MT5 bağlantısı başarısız, program sonlandırılıyor")
        return False

    def get_data(self, bars=500):
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
        ema1 = data.ewm(span=period).mean()
        ema2 = ema1.ewm(span=period).mean()
        return 2 * ema1 - ema2

    def calculate_supertrend(self, df):
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

    def find_pivot_points(self, df):
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

    def calculate_supply_demand_zones(self, df):
        high = df['high'].values
        low = df['low'].values
        volume = df['tick_volume'].values
        price_max = np.max(high[-100:])
        price_min = np.min(low[-100:])
        price_range = price_max - price_min
        division_size = price_range / self.resolution_div
        total_volume = np.sum(volume[-100:])
        threshold_volume = total_volume * self.supply_demand_threshold / 100
        supply_zones = []
        demand_zones = []
        current_level = price_max
        for _ in range(self.resolution_div):
            level_volume = sum(
                volume[j] for j in range(-100, 0)
                if len(high) + j >= 0 and high[j] >= current_level - division_size and low[j] <= current_level
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
        current_level = price_min
        for _ in range(self.resolution_div):
            level_volume = sum(
                volume[j] for j in range(-100, 0)
                if len(high) + j >= 0 and high[j] >= current_level and low[j] <= current_level + division_size
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

    def generate_signals(self, df):
        if len(df) < self.media3_period:
            self.logger.debug("Yetersiz veri, sinyal üretilemedi")
            return None
        close = df['close'].values
        dema1 = self.calculate_dema(df['close'], self.media1_period)
        dema2 = self.calculate_dema(df['close'], self.media2_period)
        dema3 = self.calculate_dema(df['close'], self.media3_period)
        trend, supertrend = self.calculate_supertrend(df)
        pivot_highs, pivot_lows = self.find_pivot_points(df)
        sr_levels = self.calculate_support_resistance(pivot_highs, pivot_lows, df)
        supply_zones, demand_zones = self.calculate_supply_demand_zones(df)
        current_price = close[-1]
        previous_price = close[-2]
        current_time = df['time'].iloc[-1]
        signal = None
        signal_strength = 0
        if len(trend) > 1:
            if trend[-1] == 1 and trend[-2] == -1:
                signal = "BUY"
                signal_strength += 3
                self.logger.debug(f"SuperTrend BUY sinyali: {current_price}")
            elif trend[-1] == -1 and trend[-2] == 1:
                signal = "SELL"
                signal_strength += 3
                self.logger.debug(f"SuperTrend SELL sinyali: {current_price}")
        if len(dema1) > 1 and len(dema2) > 1 and len(dema3) > 1:
            ma1_current = dema1.iloc[-1]
            ma2_current = dema2.iloc[-1]
            ma3_current = dema3.iloc[-1]
            if ma1_current > ma2_current > ma3_current and current_price > ma1_current:
                signal = "BUY" if signal is None else signal
                signal_strength += 2 if signal == "BUY" else 1
                self.logger.debug(f"MA BUY sinyali: MA1={ma1_current}, MA2={ma2_current}, MA3={ma3_current}")
            elif ma1_current < ma2_current < ma3_current and current_price < ma1_current:
                signal = "SELL" if signal is None else signal
                signal_strength += 2 if signal == "SELL" else 1
                self.logger.debug(f"MA SELL sinyali: MA1={ma1_current}, MA2={ma2_current}, MA3={ma3_current}")
        for level in sr_levels:
            level_price = level['level']
            if previous_price <= level_price < current_price:
                if signal == "BUY":
                    signal_strength += level['strength']
                self.logger.debug(f"Resistance kırıldı: {level_price}, Güç: {level['strength']}")
            elif previous_price >= level_price > current_price:
                if signal == "SELL":
                    signal_strength += level['strength']
                self.logger.debug(f"Support kırıldı: {level_price}, Güç: {level['strength']}")
        for zone in supply_zones:
            if zone['low'] <= current_price <= zone['high']:
                if signal == "SELL":
                    signal_strength += 1
                self.logger.debug(f"Supply zone'da: {zone['low']}-{zone['high']}, Güç: {zone['strength']}")
        for zone in demand_zones:
            if zone['low'] <= current_price <= zone['high']:
                if signal == "BUY":
                    signal_strength += 1
                self.logger.debug(f"Demand zone'da: {zone['low']}-{zone['high']}, Güç: {zone['strength']}")
        if len(pivot_highs) > 0:
            last_pivot_high = pivot_highs[-1][1]
            if abs(current_price - last_pivot_high) / current_price < self.pivot_proximity_threshold:
                if signal == "SELL" or signal is None:
                    signal = "STRONG_SELL"
                    signal_strength += 2
                    self.logger.info(f"Güçlü SELL sinyali - Pivot High: {last_pivot_high}")
        if len(pivot_lows) > 0:
            last_pivot_low = pivot_lows[-1][1]
            if abs(current_price - last_pivot_low) / current_price < self.pivot_proximity_threshold:
                if signal == "BUY" or signal is None:
                    signal = "STRONG_BUY"
                    signal_strength += 2
                    self.logger.info(f"Güçlü BUY sinyali - Pivot Low: {last_pivot_low}")
        if (self.last_signal_time is not None and
                self.last_signal == signal and
                (current_time - self.last_signal_time).total_seconds() < 300):
            self.logger.debug(f"Aynı sinyal tekrarlandı, işlem yapılmadı: {signal}")
            return None
        if signal and signal_strength >= self.min_signal_strength:
            self.logger.debug(f"Sinyal üretildi: {signal}, Güç: {signal_strength}")
            self.last_signal = signal
            self.last_signal_time = current_time
            return {
                'signal': signal,
                'strength': signal_strength,
                'price': current_price,
                'ma1': dema1.iloc[-1],
                'ma2': dema2.iloc[-1],
                'ma3': dema3.iloc[-1],
                'supertrend': supertrend[-1],
                'trend': trend[-1],
                'sr_levels': sr_levels,
                'supply_zones': supply_zones,
                'demand_zones': demand_zones
            }
        self.logger.debug(f"Sinyal üretilmedi veya güç yetersiz: {signal_strength}")
        return None

    def calculate_stop_loss_take_profit(self, signal_data):
        current_price = signal_data['price']
        signal = signal_data['signal']
        atr = self.get_atr()
        if signal in ["BUY", "STRONG_BUY"]:
            stop_loss = current_price - (2 * atr)
            take_profit = current_price + (3 * atr)
            for level in signal_data['sr_levels']:
                if level['level'] < current_price:
                    stop_loss = max(stop_loss, level['level'] - 0.0005)
                    break
        elif signal in ["SELL", "STRONG_SELL"]:
            stop_loss = current_price + (2 * atr)
            take_profit = current_price - (3 * atr)
            for level in signal_data['sr_levels']:
                if level['level'] > current_price:
                    stop_loss = min(stop_loss, level['level'] + 0.0005)
                    break
        else:
            self.logger.debug("Geçersiz sinyal, SL/TP hesaplanamadı")
            return None, None
        self.logger.debug(f"SL: {stop_loss}, TP: {take_profit}")
        return stop_loss, take_profit

    def get_atr(self):
        df = self.get_data(50)
        if df is None:
            self.logger.debug("ATR için veri alınamadı, varsayılan değer: 0.001")
            return 0.001
        atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=self.atr_period)
        return atr[-1] if len(atr) > 0 else 0.001

    def check_margin_level(self):
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("Hesap bilgileri alınamadı. MT5 bağlantısını kontrol edin.")
            return False
        margin_level = account_info.margin_level
        self.logger.debug(f"Marjin seviyesi: {margin_level}%, Bakiye: {account_info.balance}, Marjin: {account_info.margin}, Serbest Marjin: {account_info.margin_free}, Özkaynak: {account_info.equity}")
        if margin_level == 0.0 and account_info.margin == 0.0 and account_info.margin_free == account_info.balance:
            self.logger.info("Açık pozisyon yok, marjin seviyesi sıfır görünüyor. İşleme izin veriliyor.")
            return True
        if margin_level < self.min_margin_level:
            self.logger.warning(f"Marjin seviyesi yetersiz: {margin_level}% (Minimum: {self.min_margin_level}%)")
            return False
        self.logger.debug(f"Marjin seviyesi uygun: {margin_level}%")
        return True

    def count_positions(self, position_type):
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return 0
        count = sum(1 for pos in positions if pos.magic == self.magic_number and pos.type == position_type)
        self.logger.debug(f"{position_type} pozisyon sayısı: {count}")
        return count

    def place_order(self, order_type, stop_loss, take_profit, lot_size=None):
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
            "comment": "MegaTrendBot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Emir başarısız: {result.retcode if result else 'None'} - {result.comment if result else 'Bilinmeyen hata'}")
            return False
        self.logger.info(f"Emir başarılı: {result.order} - {'BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL'} - {volume} lot")
        return True

    def close_positions(self, position_type=None):
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            self.logger.debug("Kapatılacak pozisyon yok")
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
                "comment": "Close by MegaTrendBot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(close_request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"Pozisyon kapatıldı: {position.ticket}")
            else:
                self.logger.error(f"Pozisyon kapatılamadı: {result.comment}")

    def run_bot(self):
        self.logger.info("MegaTrend Bot başlatıldı...")
        if not self.initialize_mt5():
            self.logger.error("Bot başlatılamadı. Program sonlandırılıyor.")
            return
        while True:
            try:
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
                if not self.check_margin_level():
                    self.logger.warning("Marjin seviyesi yetersiz. İşlem yapılmadı.")
                    time.sleep(10)
                    continue
                buy_count = self.count_positions(mt5.POSITION_TYPE_BUY)
                sell_count = self.count_positions(mt5.POSITION_TYPE_SELL)
                if signal in ["BUY", "STRONG_BUY"] and buy_count < self.max_positions:
                    lot_size = self.lot_size if buy_count == 0 else self.lot_size / 2
                    sl, tp = self.calculate_stop_loss_take_profit(signal_data)
                    if sl is None or tp is None:
                        self.logger.debug("SL veya TP hesaplanamadı, işlem yapılmadı")
                        time.sleep(5)
                        continue
                    if sell_count > 0 and signal == "STRONG_BUY":
                        self.close_positions(mt5.POSITION_TYPE_SELL)
                        self.logger.info(f"Ters sinyal - SELL pozisyonları kapatıldı: {signal}")
                    if self.place_order(mt5.ORDER_TYPE_BUY, sl, tp, lot_size):
                        self.logger.info(f"BUY emri verildi - Güç: {strength}, SL: {sl}, TP: {tp}, Lot: {lot_size}")
                elif signal in ["SELL", "STRONG_SELL"] and sell_count < self.max_positions:
                    lot_size = self.lot_size if sell_count == 0 else self.lot_size / 2
                    sl, tp = self.calculate_stop_loss_take_profit(signal_data)
                    if sl is None or tp is None:
                        self.logger.debug("SL veya TP hesaplanamadı, işlem yapılmadı")
                        time.sleep(5)
                        continue
                    if buy_count > 0 and signal == "STRONG_SELL":
                        self.close_positions(mt5.POSITION_TYPE_BUY)
                        self.logger.info(f"Ters sinyal - BUY pozisyonları kapatıldı: {signal}")
                    if self.place_order(mt5.ORDER_TYPE_SELL, sl, tp, lot_size):
                        self.logger.info(f"SELL emri verildi - Güç: {strength}, SL: {sl}, TP: {tp}, Lot: {lot_size}")
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
    bot = MegaTrendBot(symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M5, lot_size=0.01)
    bot.run_bot()