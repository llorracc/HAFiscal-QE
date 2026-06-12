"""
HAFiscal Deep Progress Tracking and Performance Profiling

Provides comprehensive monitoring for computational reproduction:
- Real-time progress logging to /tmp/hafiscal_progress.log
- Hierarchical timing with call stacks
- Loop progress tracking with ETA estimation
- Memory monitoring
- Bottleneck identification
- Optimization recommendations

Usage:
    from hafiscal_progress import profiler
    
    profiler.start_step(1, "Estimating splurge factor")
    with profiler.profile_function("optimization_loop"):
        # ... code ...
    profiler.complete_step(1)

Monitor: tail -f /tmp/hafiscal_progress.log
Status:  python hafiscal_progress.py --status
Report:  python hafiscal_progress.py --report
"""

import os
import sys
import time
import json
import atexit
import functools
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any, Callable
from copy import deepcopy

# Try to import psutil for memory monitoring, but don't fail if not available
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Try to import numpy for numerical operations
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ============================================================================
# FILE LOCATIONS
# ============================================================================
PROGRESS_FILE = "/tmp/hafiscal_progress.log"
STATUS_FILE = "/tmp/hafiscal_status.json"
HEARTBEAT_FILE = "/tmp/hafiscal_heartbeat"
TIMING_FILE = "/tmp/hafiscal_timing.json"
PROFILE_FILE = "/tmp/hafiscal_profile.json"
TIMING_HISTORY_DIR = Path.home() / ".hafiscal" / "timing_history"

# ============================================================================
# DATA STRUCTURES FOR DEEP PROFILING
# ============================================================================

@dataclass
class FunctionProfile:
    """Profile data for a single function/operation"""
    name: str
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    total_memory_delta: float = 0.0
    input_sizes: List[int] = field(default_factory=list)
    
    @property
    def avg_time(self) -> float:
        return self.total_time / max(self.call_count, 1)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "call_count": self.call_count,
            "total_time": round(self.total_time, 3),
            "avg_time": round(self.avg_time, 3),
            "min_time": round(self.min_time, 3) if self.min_time != float('inf') else 0,
            "max_time": round(self.max_time, 3),
            "total_memory_delta_mb": round(self.total_memory_delta, 1),
        }

@dataclass  
class LoopProfile:
    """Profile data for a loop construct"""
    name: str
    total_iterations: int = 0
    completed_iterations: int = 0
    iteration_times: List[float] = field(default_factory=list)
    last_metrics: Dict[str, float] = field(default_factory=dict)
    
    @property
    def avg_iteration_time(self) -> float:
        if not self.iteration_times:
            return 0.0
        # Use recent iterations for better ETA
        recent = self.iteration_times[-10:] if len(self.iteration_times) > 10 else self.iteration_times
        return sum(recent) / len(recent)
    
    @property
    def eta_seconds(self) -> float:
        remaining = self.total_iterations - self.completed_iterations
        return remaining * self.avg_iteration_time
    
    @property
    def total_time(self) -> float:
        return sum(self.iteration_times)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "total_iterations": self.total_iterations,
            "completed_iterations": self.completed_iterations,
            "total_time": round(self.total_time, 2),
            "avg_iteration_time": round(self.avg_iteration_time, 3),
            "eta_seconds": round(self.eta_seconds, 1),
        }

@dataclass
class OptimizationOpportunity:
    """Identified optimization opportunity"""
    location: str
    category: str  # 'parallelization', 'caching', 'algorithm', 'memory'
    description: str
    estimated_speedup: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    priority: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class StepProfile:
    """Profile data for a major step"""
    step_num: int
    description: str
    start_time: float = 0.0
    end_time: float = 0.0
    substeps: List[str] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        if self.end_time > 0:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    def to_dict(self) -> dict:
        return {
            "step_num": self.step_num,
            "description": self.description,
            "duration_seconds": round(self.duration, 2),
            "substeps": self.substeps,
        }

# ============================================================================
# LOOP CONTEXT MANAGER HELPER
# ============================================================================

class LoopContext:
    """Context for tracking loop iterations"""
    def __init__(self, profiler: 'DeepProfiler', profile: LoopProfile):
        self.profiler = profiler
        self.profile = profile
        self.iter_start = None
        self._last_log_time = 0
    
    def iteration(self, i: int, metrics: Dict[str, float] = None):
        """Call at the start of each iteration"""
        now = time.time()
        
        if self.iter_start is not None:
            # Record previous iteration time
            iter_time = now - self.iter_start
            self.profile.iteration_times.append(iter_time)
        
        self.profile.completed_iterations = i + 1
        self.iter_start = now
        
        if metrics:
            self.profile.last_metrics = metrics
        
        # Log progress: every 5% or every 30 seconds or if metrics provided
        should_log = False
        total = self.profile.total_iterations
        pct_interval = max(1, total // 20)
        
        if i % pct_interval == 0:
            should_log = True
        if now - self._last_log_time > 30:
            should_log = True
        if metrics:
            should_log = True
        
        if should_log:
            self._last_log_time = now
            eta = self.profile.eta_seconds
            pct = (i + 1) / total * 100
            metrics_str = ""
            if metrics:
                metrics_str = " | " + ", ".join(f"{k}={v:.4f}" for k, v in metrics.items())
            self.profiler.log(
                f"    [{i+1}/{total}] {pct:5.1f}% | "
                f"ETA: {self.profiler._format_duration(eta)}{metrics_str}",
                "ITER"
            )
            self.profiler._update_status()

# ============================================================================
# DEEP PROFILER CLASS
# ============================================================================

class DeepProfiler:
    """
    Comprehensive profiler for HAFiscal computational reproduction.
    
    Features:
    - Hierarchical timing with call stacks
    - Loop progress tracking with ETA
    - Memory monitoring
    - Automatic bottleneck identification
    - Optimization recommendations
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Only initialize once (singleton pattern)
        if DeepProfiler._initialized:
            return
        DeepProfiler._initialized = True
        
        self.start_time = time.time()
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Timing data structures
        self.function_profiles: Dict[str, FunctionProfile] = {}
        self.loop_profiles: Dict[str, LoopProfile] = {}
        self.step_profiles: Dict[int, StepProfile] = {}
        self.call_stack: List[str] = []
        
        # Current state tracking
        self.current_step = 0
        self.current_substep = ""
        self.total_steps = 5
        self._enabled = True
        
        # Memory tracking
        if HAS_PSUTIL:
            self.process = psutil.Process()
        else:
            self.process = None
        self.memory_samples: List[Dict] = []
        
        # Optimization opportunities
        self.opportunities: List[OptimizationOpportunity] = []
        
        # Ensure directories exist
        try:
            TIMING_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        
        # Initialize log
        self._init_log()
        
        # Register cleanup on exit
        atexit.register(self._finalize)
    
    def _init_log(self):
        """Initialize the progress log file"""
        try:
            with open(PROGRESS_FILE, "w") as f:
                f.write(f"{'='*80}\n")
                f.write(f"HAFiscal Deep Profiling Session\n")
                f.write(f"Run ID: {self.run_id}\n")
                f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"PID: {os.getpid()}\n")
                f.write(f"{'='*80}\n\n")
        except Exception as e:
            print(f"Warning: Could not initialize progress log: {e}")
    
    def enable(self):
        """Enable profiling"""
        self._enabled = True
    
    def disable(self):
        """Disable profiling (no-op mode)"""
        self._enabled = False
    
    def log(self, message: str, level: str = "INFO"):
        """Write timestamped message to progress log"""
        if not self._enabled:
            return
            
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            elapsed = time.time() - self.start_time
            elapsed_str = self._format_duration(elapsed)
            
            if self.process and HAS_PSUTIL:
                mem_mb = self.process.memory_info().rss / 1024 / 1024
                mem_str = f"[{mem_mb:6.0f}MB]"
            else:
                mem_str = ""
            
            line = f"[{timestamp}] [{elapsed_str:>8}] {mem_str} [{level:8}] {message}\n"
            
            with open(PROGRESS_FILE, "a") as f:
                f.write(line)
            
            # Update heartbeat
            Path(HEARTBEAT_FILE).write_text(f"{time.time()}\n{message}")
        except Exception:
            pass  # Don't let logging errors break the computation
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable form"""
        if seconds < 60:
            return f"{seconds:5.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:5.1f}m"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours:2d}h{mins:02d}m"
    
    def _get_memory_mb(self) -> float:
        """Get current memory usage in MB"""
        if self.process and HAS_PSUTIL:
            return self.process.memory_info().rss / 1024 / 1024
        return 0.0
    
    # ========================================================================
    # STEP/SUBSTEP TRACKING
    # ========================================================================
    
    def start_step(self, step_num: int, description: str, total_steps: int = None):
        """Mark the start of a major computational step"""
        if not self._enabled:
            return
            
        if total_steps:
            self.total_steps = total_steps
            
        self.current_step = step_num
        self.current_substep = description
        
        self.step_profiles[step_num] = StepProfile(
            step_num=step_num,
            description=description,
            start_time=time.time()
        )
        
        self.log(f"{'='*70}", "STEP")
        self.log(f"STEP {step_num}/{self.total_steps}: {description}", "STEP")
        self.log(f"{'='*70}", "STEP")
        
        self._update_status()
    
    def substep(self, description: str, expected_duration_min: float = None):
        """Log a substep with optional expected duration"""
        if not self._enabled:
            return
            
        self.current_substep = description
        
        if self.current_step in self.step_profiles:
            self.step_profiles[self.current_step].substeps.append(description)
        
        eta_str = f" [ETA: ~{expected_duration_min:.0f} min]" if expected_duration_min else ""
        self.log(f"→ {description}{eta_str}", "SUBSTEP")
        self._update_status()
    
    def complete_step(self, step_num: int):
        """Mark step completion and show breakdown"""
        if not self._enabled:
            return
            
        if step_num in self.step_profiles:
            self.step_profiles[step_num].end_time = time.time()
            duration = self.step_profiles[step_num].duration
            duration_str = self._format_duration(duration)
        else:
            duration_str = "unknown"
        
        self.log(f"{'='*70}", "COMPLETE")
        self.log(f"✓ STEP {step_num} COMPLETE - Duration: {duration_str}", "COMPLETE")
        self._show_step_breakdown(step_num)
        self.log(f"{'='*70}", "COMPLETE")
        
        self._update_status()
        self._save_intermediate()
    
    def progress(self, message: str):
        """Log a progress message"""
        self.log(f"  {message}", "PROGRESS")
    
    # ========================================================================
    # FUNCTION TIMING
    # ========================================================================
    
    @contextmanager
    def profile_function(self, func_name: str, input_size: int = None):
        """
        Profile a function call with timing and memory tracking.
        
        Usage:
            with profiler.profile_function("solve_agent", input_size=len(agents)):
                result = solve_all_agents()
        """
        if not self._enabled:
            yield None
            return
        
        full_name = "/".join(self.call_stack + [func_name]) if self.call_stack else func_name
        self.call_stack.append(func_name)
        
        # Initialize profile if needed
        if full_name not in self.function_profiles:
            self.function_profiles[full_name] = FunctionProfile(name=full_name)
        
        profile = self.function_profiles[full_name]
        
        # Record start state
        start_time = time.time()
        start_mem = self._get_memory_mb()
        
        if input_size is not None:
            profile.input_sizes.append(input_size)
        
        # Only log for significant functions (not deeply nested)
        if len(self.call_stack) <= 3:
            self.log(f"  ▶ {func_name} started", "FUNC")
        
        try:
            yield profile
        finally:
            # Record end state
            duration = time.time() - start_time
            mem_delta = self._get_memory_mb() - start_mem
            
            # Update profile
            profile.call_count += 1
            profile.total_time += duration
            profile.min_time = min(profile.min_time, duration)
            profile.max_time = max(profile.max_time, duration)
            profile.total_memory_delta += mem_delta
            
            self.call_stack.pop()
            
            # Only log for significant functions
            if len(self.call_stack) <= 2:
                duration_str = self._format_duration(duration)
                mem_str = f", Δmem: {mem_delta:+.1f}MB" if abs(mem_delta) > 1 else ""
                self.log(f"  ◀ {func_name} finished [{duration_str}{mem_str}]", "FUNC")
            
            # Check for optimization opportunities
            self._check_function_opportunities(profile)
    
    def record_time(self, operation_name: str, duration_seconds: float, details: str = ""):
        """Record timing for an operation (for cases where context manager isn't suitable)"""
        if not self._enabled:
            return
            
        if operation_name not in self.function_profiles:
            self.function_profiles[operation_name] = FunctionProfile(name=operation_name)
        
        profile = self.function_profiles[operation_name]
        profile.call_count += 1
        profile.total_time += duration_seconds
        profile.min_time = min(profile.min_time, duration_seconds)
        profile.max_time = max(profile.max_time, duration_seconds)
        
        duration_str = self._format_duration(duration_seconds)
        detail_str = f" ({details})" if details else ""
        self.log(f"  ⏱ {operation_name}{detail_str}: {duration_str}", "TIMING")
    
    # ========================================================================
    # LOOP TRACKING
    # ========================================================================
    
    @contextmanager
    def track_loop(self, loop_name: str, total_iterations: int):
        """
        Track a loop's progress with ETA estimation.
        
        Usage:
            with profiler.track_loop("nelder_mead_iterations", max_iter) as loop:
                for i in range(max_iter):
                    loop.iteration(i)
                    # ... do work ...
        """
        if not self._enabled:
            # Return a dummy context that does nothing
            class DummyLoop:
                def iteration(self, i, metrics=None):
                    pass
            yield DummyLoop()
            return
        
        if loop_name not in self.loop_profiles:
            self.loop_profiles[loop_name] = LoopProfile(name=loop_name)
        
        profile = self.loop_profiles[loop_name]
        profile.total_iterations = total_iterations
        profile.completed_iterations = 0
        profile.iteration_times = []
        
        self.log(f"  🔄 Loop '{loop_name}' starting ({total_iterations} iterations)", "LOOP")
        
        ctx = LoopContext(self, profile)
        try:
            yield ctx
        finally:
            if ctx.iter_start is not None:
                profile.iteration_times.append(time.time() - ctx.iter_start)
            
            total_time = profile.total_time
            self.log(
                f"  ✓ Loop '{loop_name}' complete: {profile.completed_iterations} iterations, "
                f"total {self._format_duration(total_time)}, "
                f"avg {self._format_duration(profile.avg_iteration_time)}/iter",
                "LOOP"
            )
    
    # ========================================================================
    # CONVERGENCE TRACKING
    # ========================================================================
    
    def log_convergence(self, iteration: int, metric_name: str, value: float, 
                        threshold: float = None, converged: bool = False):
        """Log a convergence iteration"""
        if not self._enabled:
            return
            
        status = " ✓ CONVERGED" if converged else ""
        thresh_str = f" (threshold: {threshold})" if threshold else ""
        self.log(
            f"    Iteration {iteration}: {metric_name} = {value:.6f}{thresh_str}{status}",
            "CONV"
        )
    
    # ========================================================================
    # MEMORY MONITORING
    # ========================================================================
    
    def sample_memory(self, label: str = ""):
        """Take a memory sample for tracking memory usage over time"""
        if not self._enabled:
            return
            
        mem_mb = self._get_memory_mb()
        sample = {
            "timestamp": time.time(),
            "elapsed": time.time() - self.start_time,
            "label": label,
            "rss_mb": mem_mb,
        }
        self.memory_samples.append(sample)
        
        if label:
            self.log(f"  📊 Memory at '{label}': {mem_mb:.0f}MB RSS", "MEM")
    
    # ========================================================================
    # OPTIMIZATION OPPORTUNITY DETECTION
    # ========================================================================
    
    def _check_function_opportunities(self, profile: FunctionProfile):
        """Check if a function profile suggests optimization opportunities"""
        if not self._enabled:
            return
            
        # Check for functions that could benefit from parallelization
        if profile.call_count > 10 and profile.avg_time > 1.0 and profile.total_time > 60:
            self.opportunities.append(OptimizationOpportunity(
                location=profile.name,
                category="parallelization",
                description=f"Function called {profile.call_count}x with avg {profile.avg_time:.1f}s - consider parallelization",
                estimated_speedup=f"~{min(profile.call_count, 4)}x with multiprocessing",
                evidence={"call_count": profile.call_count, "avg_time": profile.avg_time},
                priority="HIGH" if profile.total_time > 300 else "MEDIUM"
            ))
        
        # Check for functions with high variance (might benefit from caching)
        if profile.call_count > 5 and profile.max_time > 2 * profile.min_time and profile.min_time > 0:
            self.opportunities.append(OptimizationOpportunity(
                location=profile.name,
                category="caching",
                description=f"High variance in execution time ({profile.min_time:.1f}s to {profile.max_time:.1f}s) - consider memoization",
                estimated_speedup="Variable - depends on cache hit rate",
                evidence={"min": profile.min_time, "max": profile.max_time},
                priority="MEDIUM"
            ))
    
    def add_optimization_opportunity(self, location: str, category: str, 
                                     description: str, estimated_speedup: str,
                                     priority: str = "MEDIUM"):
        """Manually add an optimization opportunity"""
        if not self._enabled:
            return
            
        self.opportunities.append(OptimizationOpportunity(
            location=location,
            category=category,
            description=description,
            estimated_speedup=estimated_speedup,
            priority=priority
        ))
    
    # ========================================================================
    # STATUS AND REPORTING
    # ========================================================================
    
    def _update_status(self):
        """Update the status JSON file"""
        if not self._enabled:
            return
            
        try:
            elapsed = time.time() - self.start_time
            
            # Find current active loop if any
            active_loop = None
            for name, profile in self.loop_profiles.items():
                if profile.completed_iterations < profile.total_iterations and profile.total_iterations > 0:
                    active_loop = {
                        "name": name,
                        "progress": f"{profile.completed_iterations}/{profile.total_iterations}",
                        "pct": profile.completed_iterations / profile.total_iterations * 100,
                        "eta_seconds": profile.eta_seconds,
                        "eta_formatted": self._format_duration(profile.eta_seconds),
                        "last_metrics": profile.last_metrics,
                    }
                    break
            
            status = {
                "run_id": self.run_id,
                "current_step": self.current_step,
                "total_steps": self.total_steps,
                "current_substep": self.current_substep,
                "elapsed_seconds": round(elapsed, 1),
                "elapsed_formatted": self._format_duration(elapsed),
                "memory_mb": round(self._get_memory_mb(), 0),
                "active_loop": active_loop,
                "last_update": datetime.now().isoformat(),
                "call_stack": self.call_stack[-3:] if self.call_stack else [],
            }
            
            with open(STATUS_FILE, "w") as f:
                json.dump(status, f, indent=2)
        except Exception:
            pass
    
    def _show_step_breakdown(self, step_num: int):
        """Show timing breakdown for a completed step"""
        if not self._enabled:
            return
            
        # Find function profiles related to this step
        step_prefix = f"step_{step_num}"
        relevant_profiles = []
        
        for k, v in self.function_profiles.items():
            # Include profiles that might be from this step
            if v.total_time > 1:  # Only show significant items
                relevant_profiles.append(v)
        
        if not relevant_profiles:
            return
        
        self.log(f"  Step {step_num} top time consumers:", "REPORT")
        sorted_profiles = sorted(relevant_profiles, key=lambda p: p.total_time, reverse=True)
        
        total_tracked = sum(p.total_time for p in sorted_profiles)
        for p in sorted_profiles[:10]:
            if p.total_time < 1:
                continue
            pct = p.total_time / max(total_tracked, 1) * 100
            self.log(
                f"    {p.name}: {self._format_duration(p.total_time)} ({pct:.1f}%) "
                f"[{p.call_count} calls, avg {self._format_duration(p.avg_time)}]",
                "REPORT"
            )
    
    def _save_intermediate(self):
        """Save intermediate results"""
        if not self._enabled:
            return
        try:
            self._save_profile_data()
        except Exception:
            pass
    
    def _save_profile_data(self):
        """Save profile data to file"""
        profile_data = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "total_duration": time.time() - self.start_time,
            "steps": {k: v.to_dict() for k, v in self.step_profiles.items()},
            "functions": {k: v.to_dict() for k, v in self.function_profiles.items()},
            "loops": {k: v.to_dict() for k, v in self.loop_profiles.items()},
            "memory_samples": self.memory_samples[-100:],  # Last 100 samples
            "opportunities": [o.to_dict() for o in self.opportunities[-50:]],  # Last 50
            "bottlenecks": self._identify_bottlenecks(),
        }
        
        with open(PROFILE_FILE, "w") as f:
            json.dump(profile_data, f, indent=2)
        
        with open(TIMING_FILE, "w") as f:
            json.dump(profile_data, f, indent=2)
    
    def _identify_bottlenecks(self) -> List[Dict]:
        """Identify top bottlenecks"""
        total_time = time.time() - self.start_time
        if total_time < 1:
            return []
        
        bottlenecks = []
        
        sorted_profiles = sorted(
            self.function_profiles.values(),
            key=lambda p: p.total_time,
            reverse=True
        )
        
        for p in sorted_profiles[:20]:
            pct = p.total_time / total_time * 100
            if pct >= 1.0:  # At least 1% of total time
                bottlenecks.append({
                    "operation": p.name,
                    "total_seconds": round(p.total_time, 2),
                    "total_formatted": self._format_duration(p.total_time),
                    "pct_of_total": round(pct, 1),
                    "call_count": p.call_count,
                    "avg_seconds": round(p.avg_time, 2),
                    "priority": "CRITICAL" if pct > 30 else "HIGH" if pct > 15 else "MEDIUM" if pct > 5 else "LOW"
                })
        
        return bottlenecks
    
    def generate_report(self) -> str:
        """Generate comprehensive profiling report"""
        elapsed = time.time() - self.start_time
        
        lines = []
        lines.append("=" * 80)
        lines.append("HAFISCAL PERFORMANCE PROFILING REPORT")
        lines.append("=" * 80)
        lines.append(f"Run ID: {self.run_id}")
        lines.append(f"Total Duration: {self._format_duration(elapsed)}")
        if self.memory_samples:
            peak_mem = max(s.get('rss_mb', 0) for s in self.memory_samples)
            lines.append(f"Peak Memory: {peak_mem:.0f}MB")
        lines.append("")
        
        # Step summary
        lines.append("-" * 80)
        lines.append("STEP SUMMARY")
        lines.append("-" * 80)
        
        for step_num in sorted(self.step_profiles.keys()):
            sp = self.step_profiles[step_num]
            lines.append(f"Step {step_num}: {sp.description}")
            lines.append(f"  Duration: {self._format_duration(sp.duration)}")
            if sp.substeps:
                lines.append(f"  Substeps: {len(sp.substeps)}")
        
        lines.append("")
        
        # Top time consumers
        lines.append("-" * 80)
        lines.append("TOP TIME CONSUMERS (Optimization Targets)")
        lines.append("-" * 80)
        
        sorted_profiles = sorted(
            self.function_profiles.values(),
            key=lambda p: p.total_time,
            reverse=True
        )
        
        for i, p in enumerate(sorted_profiles[:15], 1):
            if p.total_time < 1:
                continue
            pct = p.total_time / max(elapsed, 1) * 100
            lines.append(f"{i:2}. {p.name}")
            lines.append(
                f"    Total: {self._format_duration(p.total_time)} ({pct:.1f}%) | "
                f"Calls: {p.call_count} | Avg: {self._format_duration(p.avg_time)}"
            )
        
        # Loop analysis
        if self.loop_profiles:
            lines.append("")
            lines.append("-" * 80)
            lines.append("LOOP ANALYSIS")
            lines.append("-" * 80)
            
            for name, profile in sorted(self.loop_profiles.items(), key=lambda x: x[1].total_time, reverse=True):
                lines.append(
                    f"{name}: {profile.completed_iterations} iterations, "
                    f"total {self._format_duration(profile.total_time)}, "
                    f"avg {self._format_duration(profile.avg_iteration_time)}/iter"
                )
        
        # Optimization opportunities
        if self.opportunities:
            lines.append("")
            lines.append("-" * 80)
            lines.append("OPTIMIZATION OPPORTUNITIES")
            lines.append("-" * 80)
            
            sorted_opps = sorted(
                self.opportunities, 
                key=lambda o: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(o.priority, 4)
            )
            
            seen = set()
            for opp in sorted_opps[:10]:
                key = (opp.location, opp.category)
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"[{opp.priority}] {opp.category.upper()}: {opp.location}")
                lines.append(f"    {opp.description}")
                lines.append(f"    Estimated speedup: {opp.estimated_speedup}")
        
        return "\n".join(lines)
    
    def _finalize(self):
        """Called on exit - save final timing and generate report"""
        if not self._enabled:
            return
            
        total_duration = time.time() - self.start_time
        
        self.log(f"\n{'='*70}", "FINAL")
        self.log(f"REPRODUCTION COMPLETE", "FINAL")
        self.log(f"Total Duration: {self._format_duration(total_duration)}", "FINAL")
        self.log(f"{'='*70}", "FINAL")
        
        # Save final profile data
        try:
            self._save_profile_data()
            
            # Save to history
            history_file = TIMING_HISTORY_DIR / f"profile_{self.run_id}.json"
            with open(PROFILE_FILE, "r") as f:
                profile_data = json.load(f)
            with open(history_file, "w") as f:
                json.dump(profile_data, f, indent=2)
            
            self.log(f"Profile data saved to: {PROFILE_FILE}", "FINAL")
            self.log(f"History saved to: {history_file}", "FINAL")
        except Exception as e:
            self.log(f"Error saving profile data: {e}", "ERROR")
        
        # Print report to log
        try:
            report = self.generate_report()
            self.log("\n" + report, "REPORT")
        except Exception as e:
            self.log(f"Error generating report: {e}", "ERROR")


# ============================================================================
# GLOBAL PROFILER INSTANCE
# ============================================================================

profiler = DeepProfiler()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def start_step(step_num: int, description: str, total_steps: int = None):
    """Convenience function to start a step"""
    profiler.start_step(step_num, description, total_steps)

def complete_step(step_num: int):
    """Convenience function to complete a step"""
    profiler.complete_step(step_num)

def substep(description: str, expected_duration_min: float = None):
    """Convenience function to log a substep"""
    profiler.substep(description, expected_duration_min)

def profile_function(func_name: str, input_size: int = None):
    """Convenience function for profiling"""
    return profiler.profile_function(func_name, input_size)

def track_loop(loop_name: str, total_iterations: int):
    """Convenience function for loop tracking"""
    return profiler.track_loop(loop_name, total_iterations)

def log_convergence(iteration: int, metric_name: str, value: float, 
                    threshold: float = None, converged: bool = False):
    """Convenience function for convergence logging"""
    profiler.log_convergence(iteration, metric_name, value, threshold, converged)

def progress(message: str):
    """Convenience function for progress messages"""
    profiler.progress(message)


# ============================================================================
# CLI INTERFACE
# ============================================================================

def print_status():
    """Print current status"""
    if Path(STATUS_FILE).exists():
        try:
            status = json.loads(Path(STATUS_FILE).read_text())
            print(f"Run ID: {status['run_id']}")
            print(f"Step: {status['current_step']}/{status['total_steps']}")
            print(f"Substep: {status['current_substep']}")
            print(f"Elapsed: {status['elapsed_formatted']}")
            print(f"Memory: {status['memory_mb']:.0f}MB")
            if status.get('active_loop'):
                loop = status['active_loop']
                print(f"Active Loop: {loop['name']} {loop['progress']} ({loop['pct']:.0f}%)")
                print(f"Loop ETA: {loop['eta_formatted']}")
                if loop.get('last_metrics'):
                    print(f"Last metrics: {loop['last_metrics']}")
            print(f"Last update: {status['last_update']}")
        except Exception as e:
            print(f"Error reading status: {e}")
    else:
        print("No active run (status file not found)")

def print_report():
    """Print profiling report"""
    if Path(PROFILE_FILE).exists():
        try:
            data = json.loads(Path(PROFILE_FILE).read_text())
            print("=" * 80)
            print("HAFISCAL PROFILING SUMMARY")
            print("=" * 80)
            print(f"Run: {data['run_id']}")
            print(f"Duration: {data['total_duration']/3600:.2f} hours ({data['total_duration']/60:.1f} minutes)")
            
            print("\n" + "-" * 80)
            print("STEP SUMMARY")
            print("-" * 80)
            for step_num, step in sorted(data.get('steps', {}).items()):
                print(f"Step {step_num}: {step['description']} - {step['duration_seconds']/60:.1f} min")
            
            print("\n" + "-" * 80)
            print("TOP TIME CONSUMERS")
            print("-" * 80)
            funcs = sorted(data.get('functions', {}).values(), key=lambda x: x['total_time'], reverse=True)
            for f in funcs[:15]:
                if f['total_time'] > 1:
                    print(f"  {f['name']}: {f['total_time']/60:.1f} min ({f['call_count']} calls)")
            
            print("\n" + "-" * 80)
            print("BOTTLENECKS")
            print("-" * 80)
            for bn in data.get('bottlenecks', [])[:10]:
                print(f"  [{bn['priority']}] {bn['operation']}: {bn['total_formatted']} ({bn['pct_of_total']:.1f}%)")
            
        except Exception as e:
            print(f"Error reading profile: {e}")
    else:
        print("No profile data. Run a reproduction first.")

def check_hang():
    """Check if the process might be hung"""
    if Path(HEARTBEAT_FILE).exists():
        try:
            content = Path(HEARTBEAT_FILE).read_text()
            lines = content.strip().split('\n')
            hb_time = float(lines[0])
            last_msg = lines[1] if len(lines) > 1 else ""
            
            diff = time.time() - hb_time
            
            if diff > 600:  # 10 minutes
                print(f"⚠️  WARNING: No progress in {diff/60:.0f} minutes")
                print(f"   Last activity: {last_msg}")
                return True
            else:
                print(f"✅ Active ({diff:.0f}s ago)")
                print(f"   Last: {last_msg}")
                return False
        except Exception as e:
            print(f"Error checking heartbeat: {e}")
            return None
    else:
        print("No heartbeat file found - process may not be running")
        return None

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "--status":
            print_status()
        
        elif cmd == "--report":
            print_report()
        
        elif cmd == "--check" or cmd == "--hang":
            check_hang()
        
        elif cmd == "--tail":
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 50
            if Path(PROGRESS_FILE).exists():
                lines = Path(PROGRESS_FILE).read_text().split('\n')
                print('\n'.join(lines[-n:]))
            else:
                print("No progress log found")
        
        elif cmd == "--bottlenecks":
            if Path(PROFILE_FILE).exists():
                data = json.loads(Path(PROFILE_FILE).read_text())
                for bn in data.get('bottlenecks', []):
                    print(f"[{bn['priority']:8}] {bn['operation']}: {bn['total_formatted']} ({bn['pct_of_total']:.1f}%)")
            else:
                print("No profile data available")
        
        elif cmd == "--opportunities":
            if Path(PROFILE_FILE).exists():
                data = json.loads(Path(PROFILE_FILE).read_text())
                for opp in data.get('opportunities', []):
                    print(f"[{opp['priority']}] {opp['category']}: {opp['location']}")
                    print(f"  {opp['description']}")
            else:
                print("No profile data")
        
        elif cmd == "--help" or cmd == "-h":
            print("HAFiscal Progress Monitor")
            print("")
            print("Usage: python hafiscal_progress.py [command]")
            print("")
            print("Commands:")
            print("  --status        Show current execution status")
            print("  --report        Show full profiling report")
            print("  --check         Check if process might be hung")
            print("  --tail [N]      Show last N lines of progress log (default 50)")
            print("  --bottlenecks   Show identified bottlenecks")
            print("  --opportunities Show optimization opportunities")
            print("")
            print("Real-time monitoring:")
            print("  tail -f /tmp/hafiscal_progress.log")
        
        else:
            print(f"Unknown command: {cmd}")
            print("Use --help for usage information")
    
    else:
        print("HAFiscal Deep Profiler")
        print("")
        print("Monitor progress:  tail -f /tmp/hafiscal_progress.log")
        print("Check status:      python hafiscal_progress.py --status")
        print("Check for hangs:   python hafiscal_progress.py --check")
        print("Full report:       python hafiscal_progress.py --report")
        print("Help:              python hafiscal_progress.py --help")
