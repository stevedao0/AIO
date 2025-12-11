# -*- coding: utf-8 -*-
"""
performance_monitor.py - Monitor hiệu suất Turbo Mode
Tạo file này trong thư mục gốc để theo dõi performance
"""
import time
import psutil
import os
from datetime import datetime


class PerformanceMonitor:
    def __init__(self):
        self.start_time = None
        self.stats = []

    def start(self):
        self.start_time = time.time()
        print("🚀 Performance Monitor Started")

    def log_stats(self, processed_count: int, total_count: int, operation: str = "Processing"):
        if not self.start_time:
            return

        current_time = time.time()
        elapsed = current_time - self.start_time

        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_gb = memory.used / (1024 ** 3)

        rate = processed_count / elapsed if elapsed > 0 else 0
        eta = (total_count - processed_count) / rate if rate > 0 else 0

        stat = {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'elapsed': elapsed,
            'processed': processed_count,
            'total': total_count,
            'rate': rate,
            'eta': eta,
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'memory_gb': memory_used_gb,
            'operation': operation
        }

        self.stats.append(stat)

        # Print real-time stats
        print(f"⚡ {operation}: {processed_count}/{total_count} | "
              f"Rate: {rate:.1f}/s | ETA: {eta:.0f}s | "
              f"CPU: {cpu_percent:.1f}% | RAM: {memory_percent:.1f}%")

    def finish(self):
        if not self.start_time:
            return

        total_time = time.time() - self.start_time
        print(f"✅ TURBO COMPLETED in {total_time:.1f}s")

        # Save detailed report
        if self.stats:
            report_path = f"turbo_performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("TURBO MODE PERFORMANCE REPORT\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Total Duration: {total_time:.2f} seconds\n")
                f.write(f"Peak CPU: {max(s['cpu_percent'] for s in self.stats):.1f}%\n")
                f.write(f"Peak Memory: {max(s['memory_percent'] for s in self.stats):.1f}%\n")
                f.write(f"Average Rate: {sum(s['rate'] for s in self.stats) / len(self.stats):.1f} items/sec\n\n")

                f.write("DETAILED LOG:\n")
                f.write("-" * 30 + "\n")
                for stat in self.stats:
                    f.write(f"{stat['timestamp']} | {stat['operation']} | "
                            f"{stat['processed']}/{stat['total']} | "
                            f"Rate: {stat['rate']:.1f}/s | "
                            f"CPU: {stat['cpu_percent']:.1f}% | "
                            f"RAM: {stat['memory_percent']:.1f}%\n")

            print(f"📊 Performance report saved: {report_path}")


# Singleton instance
monitor = PerformanceMonitor()

# Usage in your code:
# from performance_monitor import monitor
# monitor.start()
# monitor.log_stats(current_count, total_count, "Scraping")
# monitor.finish()