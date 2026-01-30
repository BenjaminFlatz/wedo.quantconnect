from AlgorithmImports import *
from QuantConnect.Indicators import *
from datetime import timedelta

class ExtendedMultiAssetCryptoMomentum(QCAlgorithm):
    
    def Initialize(self):
        self.SetStartDate(2017, 1, 1)  # Extended backtest start
        self.SetEndDate(datetime.now())  # To current date
        self.SetCash(100000)  # Starting capital
        
        # Universe: Multiple crypto pairs for diversification
        self.symbols = [self.AddCrypto(pair, Resolution.Hour).Symbol for pair in ["BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD"]]
        self.UniverseSettings.Resolution = Resolution.Hour
        self.SetUniverseSelection(ManualUniverseSelectionModel(self.symbols))
        
        # Per-symbol indicators
        self.dc = {sym: DonchianChannel(5) for sym in self.symbols}
        self.atr = {sym: self.ATR(sym, 14, MovingAverageType.Simple, Resolution.Hour) for sym in self.symbols}
        for sym in self.symbols:
            self.RegisterIndicator(sym, self.dc[sym], Resolution.Hour)
        
        # Set leverage for all
        for sym in self.symbols:
            self.Securities[sym].SetLeverage(5)
        
        # Framework models
        self.SetAlpha(CustomAlphaModel(self))
        self.SetPortfolioConstruction(InsightWeightingPortfolioConstructionModel())  # Weights by insight
        self.SetExecution(ImmediateExecutionModel())
        self.SetRiskManagement(TrailingStopRiskManagementModel(0.02))  # 2% trailing stop
        
        # Warm-up
        self.SetWarmUp(timedelta(days=1))

    def OnWarmUpFinished(self):
        # Force test trade after warm-up to ensure data readiness
        btc = self.symbols[0]  # BTCUSD
        if self.Securities[btc].Price > 0:
            self.Debug("Forcing a test buy order after warm-up.")
            self.SetHoldings(btc, 0.01)  # Small 1% on BTC

    def OnData(self, data):
        if self.IsWarmingUp: return
        for sym in self.symbols:
            bar = data.Bars.get(sym)
            if bar is None: continue
            
            if bar.Close >= self.dc[sym].UpperBand.Current.Value:
                self.Debug(f"Manual long order test triggered for {sym.Value}!")
                self.SetHoldings(sym, 0.1)
            elif bar.Close <= self.dc[sym].LowerBand.Current.Value:
                self.Debug(f"Manual short order test triggered for {sym.Value}!")
                self.SetHoldings(sym, -0.1)

class CustomAlphaModel(AlphaModel):
    def __init__(self, algorithm):
        self.algorithm = algorithm
    
    def Update(self, algorithm, data):
        insights = []
        
        for sym in self.algorithm.symbols:  # Loop over stored list
            if not (self.algorithm.dc[sym].IsReady and self.algorithm.atr[sym].IsReady):
                algorithm.Debug(f"Indicators not ready for {sym.Value}.")
                continue
            
            bar = data.Bars.get(sym)
            if bar is None or bar.Close == 0:  # Skip if no data (e.g., sparse pre-2018)
                algorithm.Debug(f"No valid bar data for {sym.Value}.")
                continue
            
            # Daily summary log per asset (reduced frequency)
            if algorithm.Time.hour == 0:
                algorithm.Debug(f"Date: {algorithm.Time} | Asset: {sym.Value} | Close: {bar.Close} | DC Upper: {self.algorithm.dc[sym].UpperBand.Current.Value} | DC Lower: {self.algorithm.dc[sym].LowerBand.Current.Value} | Volume: {bar.Volume} | ATR: {self.algorithm.atr[sym].Current.Value}")
            
            # Adaptive weight (2% risk per trade)
            if self.algorithm.atr[sym].Current.Value > 0:
                risk_per_trade = algorithm.Portfolio.TotalPortfolioValue * 0.02
                stop_distance = self.algorithm.atr[sym].Current.Value * 1.5
                weight = risk_per_trade / (bar.Close * stop_distance)
                weight = min(weight, 0.2)
            else:
                weight = 0.2
            
            # No-filter breakout signals
            if bar.Close >= self.algorithm.dc[sym].UpperBand.Current.Value:
                algorithm.Debug(f"Long signal triggered for {sym.Value}! (No filters)")
                insights.append(Insight.Price(sym, timedelta(hours=48), InsightDirection.Up, 0.10, weight=weight))
            elif bar.Close <= self.algorithm.dc[sym].LowerBand.Current.Value:
                algorithm.Debug(f"Short signal triggered for {sym.Value}! (No filters)")
                insights.append(Insight.Price(sym, timedelta(hours=48), InsightDirection.Down, 0.10, weight=weight))
        
        return insights
