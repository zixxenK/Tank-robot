#!/usr/bin/env python3
"""Feature extraction from telemetry data for machine learning training."""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

try:
    from scipy.stats import skew
except ImportError:  # Keep offline/runtime imports usable without optional SciPy.
    def skew(values: np.ndarray) -> float:
        """Return the biased Fisher-Pearson skewness using NumPy only."""
        values = np.asarray(values, dtype=float)
        centered = values - np.mean(values)
        second_moment = np.mean(centered ** 2)
        if second_moment == 0.0:
            return 0.0
        return float(np.mean(centered ** 3) / second_moment ** 1.5)


@dataclass
class FeatureSet:
    """Extracted features for a time window of telemetry."""
    # Time domain features
    mean_linear_cmd: float
    std_linear_cmd: float
    mean_angular_cmd: float
    std_angular_cmd: float
    
    # Encoder features
    mean_encoder_left: float
    mean_encoder_right: float
    encoder_diff_mean: float
    encoder_diff_std: float
    
    # IMU features
    imu_accel_magnitude_mean: float
    imu_accel_magnitude_std: float
    imu_gyro_magnitude_mean: float
    imu_gyro_magnitude_std: float
    imu_accel_x_skew: float
    imu_accel_y_skew: float
    imu_accel_z_skew: float
    
    # Battery features
    battery_voltage_mean: float
    battery_voltage_std: float
    battery_current_mean: float
    
    # Odometry features
    velocity_mean: float
    angular_velocity_mean: float
    position_change: float
    heading_change: float
    
    # Safety features
    estop_active_ratio: float
    bridge_alive_ratio: float
    
    # Label (for supervised learning)
    label: Optional[int] = None  # 0=normal, 1=anomaly, 2=success, 3=failure


class FeatureExtractor:
    """Extract features from telemetry samples for ML training."""

    def __init__(self, window_size: int = 100, overlap: int = 50) -> None:
        """
        Initialize feature extractor.
        
        Args:
            window_size: Number of samples per window
            overlap: Number of samples to overlap between windows
        """
        self._window_size = window_size
        self._overlap = overlap
        self._step = window_size - overlap

    def extract_from_samples(self, samples: List[Dict]) -> List[FeatureSet]:
        """Extract features from a list of telemetry samples."""
        if len(samples) < self._window_size:
            return []

        features: List[FeatureSet] = []
        
        for i in range(0, len(samples) - self._window_size + 1, self._step):
            window = samples[i:i + self._window_size]
            feature_set = self._extract_window_features(window)
            features.append(feature_set)

        return features

    def _extract_window_features(self, window: List[Dict]) -> FeatureSet:
        """Extract features from a single window of samples."""
        # Extract arrays
        linear_cmd = np.array([s['cmd_vel_linear'] for s in window])
        angular_cmd = np.array([s['cmd_vel_angular'] for s in window])
        encoder_left = np.array([s['encoder_left'] for s in window])
        encoder_right = np.array([s['encoder_right'] for s in window])
        imu_accel_x = np.array([s['imu_accel_x'] for s in window])
        imu_accel_y = np.array([s['imu_accel_y'] for s in window])
        imu_accel_z = np.array([s['imu_accel_z'] for s in window])
        imu_gyro_x = np.array([s['imu_gyro_x'] for s in window])
        imu_gyro_y = np.array([s['imu_gyro_y'] for s in window])
        imu_gyro_z = np.array([s['imu_gyro_z'] for s in window])
        battery_voltage = np.array([s['battery_voltage'] for s in window])
        battery_current = np.array([s['battery_current'] for s in window])
        odometry_x = np.array([s['odometry_x'] for s in window])
        odometry_y = np.array([s['odometry_y'] for s in window])
        linear_velocity = np.array([s['linear_velocity_x'] for s in window])
        angular_velocity = np.array([s['angular_velocity_z'] for s in window])
        estop_active = np.array([s['estop_active'] for s in window])
        bridge_alive = np.array([s['bridge_alive'] for s in window])

        # Compute features
        imu_accel_mag = np.sqrt(imu_accel_x**2 + imu_accel_y**2 + imu_accel_z**2)
        imu_gyro_mag = np.sqrt(imu_gyro_x**2 + imu_gyro_y**2 + imu_gyro_z**2)
        encoder_diff = encoder_right - encoder_left

        # Position and heading changes
        position_change = np.sqrt(
            (odometry_x[-1] - odometry_x[0])**2 + 
            (odometry_y[-1] - odometry_y[0])**2
        )
        
        # Approximate heading change from angular velocity integral
        heading_change = np.sum(angular_velocity) * (1.0 / 50.0)  # Assuming 50Hz

        return FeatureSet(
            # Time domain features
            mean_linear_cmd=float(np.mean(linear_cmd)),
            std_linear_cmd=float(np.std(linear_cmd)),
            mean_angular_cmd=float(np.mean(angular_cmd)),
            std_angular_cmd=float(np.std(angular_cmd)),
            
            # Encoder features
            mean_encoder_left=float(np.mean(encoder_left)),
            mean_encoder_right=float(np.mean(encoder_right)),
            encoder_diff_mean=float(np.mean(encoder_diff)),
            encoder_diff_std=float(np.std(encoder_diff)),
            
            # IMU features
            imu_accel_magnitude_mean=float(np.mean(imu_accel_mag)),
            imu_accel_magnitude_std=float(np.std(imu_accel_mag)),
            imu_gyro_magnitude_mean=float(np.mean(imu_gyro_mag)),
            imu_gyro_magnitude_std=float(np.std(imu_gyro_mag)),
            imu_accel_x_skew=float(skew(imu_accel_x)),
            imu_accel_y_skew=float(skew(imu_accel_y)),
            imu_accel_z_skew=float(skew(imu_accel_z)),
            
            # Battery features
            battery_voltage_mean=float(np.mean(battery_voltage)),
            battery_voltage_std=float(np.std(battery_voltage)),
            battery_current_mean=float(np.mean(battery_current)),
            
            # Odometry features
            velocity_mean=float(np.mean(linear_velocity)),
            angular_velocity_mean=float(np.mean(angular_velocity)),
            position_change=float(position_change),
            heading_change=float(heading_change),
            
            # Safety features
            estop_active_ratio=float(np.mean(estop_active)),
            bridge_alive_ratio=float(np.mean(bridge_alive)),
        )

    def extract_frequency_features(self, samples: List[Dict]) -> Dict[str, np.ndarray]:
        """Extract frequency domain features using FFT."""
        if len(samples) < self._window_size:
            return {}

        window = samples[:self._window_size]
        encoder_left = np.array([s['encoder_left'] for s in window])
        encoder_right = np.array([s['encoder_right'] for s in window])
        imu_accel_x = np.array([s['imu_accel_x'] for s in window])
        
        # Compute FFT
        fft_encoder_left = np.fft.fft(encoder_left)
        fft_encoder_right = np.fft.fft(encoder_right)
        fft_accel_x = np.fft.fft(imu_accel_x)
        
        # Power spectral density
        psd_encoder_left = np.abs(fft_encoder_left)**2
        psd_encoder_right = np.abs(fft_encoder_right)**2
        psd_accel_x = np.abs(fft_accel_x)**2
        
        return {
            'psd_encoder_left': psd_encoder_left,
            'psd_encoder_right': psd_encoder_right,
            'psd_accel_x': psd_accel_x,
        }

    def add_labels(self, features: List[FeatureSet], label: int) -> List[FeatureSet]:
        """Add labels to feature sets for supervised learning."""
        for feature in features:
            feature.label = label
        return features

    def export_to_numpy(self, features: List[FeatureSet], output_path: str) -> None:
        """Export features to numpy arrays for ML training."""
        if not features:
            print("No features to export")
            return

        # Convert to numpy array
        feature_arrays = []
        labels = []
        
        for feature in features:
            feature_dict = {
                'mean_linear_cmd': feature.mean_linear_cmd,
                'std_linear_cmd': feature.std_linear_cmd,
                'mean_angular_cmd': feature.mean_angular_cmd,
                'std_angular_cmd': feature.std_angular_cmd,
                'mean_encoder_left': feature.mean_encoder_left,
                'mean_encoder_right': feature.mean_encoder_right,
                'encoder_diff_mean': feature.encoder_diff_mean,
                'encoder_diff_std': feature.encoder_diff_std,
                'imu_accel_magnitude_mean': feature.imu_accel_magnitude_mean,
                'imu_accel_magnitude_std': feature.imu_accel_magnitude_std,
                'imu_gyro_magnitude_mean': feature.imu_gyro_magnitude_mean,
                'imu_gyro_magnitude_std': feature.imu_gyro_magnitude_std,
                'imu_accel_x_skew': feature.imu_accel_x_skew,
                'imu_accel_y_skew': feature.imu_accel_y_skew,
                'imu_accel_z_skew': feature.imu_accel_z_skew,
                'battery_voltage_mean': feature.battery_voltage_mean,
                'battery_voltage_std': feature.battery_voltage_std,
                'battery_current_mean': feature.battery_current_mean,
                'velocity_mean': feature.velocity_mean,
                'angular_velocity_mean': feature.angular_velocity_mean,
                'position_change': feature.position_change,
                'heading_change': feature.heading_change,
                'estop_active_ratio': feature.estop_active_ratio,
                'bridge_alive_ratio': feature.bridge_alive_ratio,
            }
            feature_arrays.append(list(feature_dict.values()))
            labels.append(feature.label if feature.label is not None else 0)

        X = np.array(feature_arrays)
        y = np.array(labels)
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        np.savez(output_file, X=X, y=y)
        print(f"Exported {len(features)} feature vectors to {output_path}")
        print(f"Feature shape: {X.shape}, Label shape: {y.shape}")


def main() -> None:
    """CLI for feature extraction."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract features from telemetry data")
    parser.add_argument("input_file", help="Input JSON file with telemetry samples")
    parser.add_argument("--output", "-o", default="features.npz", help="Output numpy file")
    parser.add_argument("--window-size", type=int, default=100, help="Window size for feature extraction")
    parser.add_argument("--overlap", type=int, default=50, help="Overlap between windows")
    parser.add_argument("--label", type=int, help="Label for supervised learning")

    args = parser.parse_args()

    # Load samples
    with open(args.input_file, 'r') as f:
        samples = json.load(f)

    # Extract features
    extractor = FeatureExtractor(window_size=args.window_size, overlap=args.overlap)
    features = extractor.extract_from_samples(samples)

    if args.label is not None:
        features = extractor.add_labels(features, args.label)

    # Export
    extractor.export_to_numpy(features, args.output)


if __name__ == "__main__":
    main()
