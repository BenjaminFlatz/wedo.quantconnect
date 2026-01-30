from AlgorithmImports import *
from QuantConnect.Indicators import *
from datetime import timedelta

class AggressiveCryptoMomentum(QCAlgorithm):
    
    def Initialize(self):
        self.SetStartDate(2020, 1, 1)  # Backtest period
        self.SetEndDate(datetime.now())
        self.SetCash(100000)  # Starting capital
        
        # Universe: Single crypto pair (BTC/USD) - Hourly for more trades
        self.btc = self.AddCrypto("BTCUSD", Resolution.Hour).Symbol
        self.UniverseSettings.Resolution = Resolution.Hour
        self.SetUniverseSelection(ManualUniverseSelectionModel([self.btc]))
        
        # Indicators
        self.dc = DonchianChannel(5)  # Short for frequent breakouts
        self.RegisterIndicator(self.btc, self.dc, Resolution.Hour)
        
        # Set leverage
        self.Securities[self.btc].SetLeverage(5)
        
        # Framework models
        self.SetAlpha(CustomAlphaModel(self))
        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel())
        self.SetExecution(ImmediateExecutionModel())
        self.SetRiskManagement(TrailingStopRiskManagementModel(0.02))  # 2% trailing stop
        
        # Warm-up
        self.SetWarmUp(timedelta(days=1))  # Shorter for hourly
        
        # Force a test trade to confirm orders work
        self.Debug("Forcing a test buy order on initialization.")
        self.SetHoldings(self.btc, 0.01)  # Small 1% portfolio buy to test

    def OnData(self, data):
        if self.IsWarmingUp: return
        bar = data.Bars.get(self.btc)
        if bar is None: return
        
        if bar.Close >= self.dc.UpperBand.Current.Value:
            self.Debug("Manual long order test triggered!")
            self.SetHoldings(self.btc, 0.1)  # Buy 10% portfolio
        elif bar.Close <= self.dc.LowerBand.Current.Value:
            self.Debug("Manual short order test triggered!")
            self.SetHoldings(self.btc, -0.1)  # Short 10% portfolio

class CustomAlphaModel(AlphaModel):
    def __init__(self, algorithm):
        self.algorithm = algorithm
    
    def Update(self, algorithm, data):
        insights = []
        
        if not self.algorithm.dc.IsReady:
            self.algorithm.Debug("Indicators not ready yet.")
            return insights
        
        bar = data.Bars.get(self.algorithm.btc)
        if bar is None:
            self.algorithm.Debug("No bar data available.")
            return insights
        
        # Log values (reduced to daily summaries to avoid rate limiting)
        if algorithm.Time.hour == 0:
            self.algorithm.Debug(f"Date: {algorithm.Time} | Close: {bar.Close} | DC Upper: {self.algorithm.dc.UpperBand.Current.Value} | DC Lower: {self.algorithm.dc.LowerBand.Current.Value} | Volume: {bar.Volume}")
        
        # Temporary: No filters to force trades
        if bar.Close >= self.algorithm.dc.UpperBand.Current.Value:
            self.algorithm.Debug("Long signal triggered! (No filters)")
            insights.append(Insight.Price(self.algorithm.btc, timedelta(hours=24), InsightDirection.Up, 0.10))
        elif bar.Close <= self.algorithm.dc.LowerBand.Current.Value:
            self.algorithm.Debug("Short signal triggered! (No filters)")
            insights.append(Insight.Price(self.algorithm.btc, timedelta(hours=24), InsightDirection.Down, 0.10))
        
        return insights
