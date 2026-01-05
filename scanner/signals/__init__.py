"""Signal detection module."""

from scanner.signals.base import SignalDetector
from scanner.signals.clustering import ClusteringDetector
from scanner.signals.contrarian import ContrarianDetector
from scanner.signals.fresh_wallet import FreshWalletDetector
from scanner.signals.odds_movement import OddsMovementDetector
from scanner.signals.size_anomaly import SizeAnomalyDetector
from scanner.signals.timing import TimingDetector

__all__ = [
    "ClusteringDetector",
    "ContrarianDetector",
    "FreshWalletDetector",
    "OddsMovementDetector",
    "SignalDetector",
    "SizeAnomalyDetector",
    "TimingDetector",
]

