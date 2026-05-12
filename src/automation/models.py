"""
数据模型定义
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


class SystemStatus(Enum):
    """系统运行状态"""
    IDLE = "idle"
    ANALYZING = "analyzing"
    TESTING = "testing"
    AUDITING = "auditing"
    PASSED = "passed"
    FAILED = "failed"
    RETRYING = "retrying"
    COMPLETED = "completed"


class Severity(Enum):
    """问题严重级别"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Issue:
    """问题描述"""
    id: str
    severity: Severity
    category: str
    title: str
    description: str
    location: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "suggestions": self.suggestions,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AnalysisReport:
    """数据分析报告"""
    report_id: str
    timestamp: datetime
    data_summary: Dict[str, Any]
    statistics: Dict[str, Any]
    issues: List[Issue] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_critical_issues(self) -> bool:
        return any(i.severity == Severity.CRITICAL for i in self.issues)
    
    @property
    def issue_count(self) -> int:
        return len(self.issues)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp.isoformat(),
            "data_summary": self.data_summary,
            "statistics": self.statistics,
            "issues": [i.to_dict() for i in self.issues],
            "recommendations": self.recommendations,
            "metadata": self.metadata,
        }
    
    def save(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


@dataclass
class TestCase:
    """测试用例"""
    id: str
    name: str
    category: str
    priority: int  # 1-5, 1 highest
    test_func: str  # 函数名
    params: Dict[str, Any] = field(default_factory=dict)
    expected: Any = None
    timeout: int = 300


@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    test_name: str
    status: str  # passed, failed, skipped, error
    duration: float
    message: str = ""
    error_details: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def is_passed(self) -> bool:
        return self.status == "passed"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "status": self.status,
            "duration": self.duration,
            "message": self.message,
            "error_details": self.error_details,
            "metrics": self.metrics,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TestSuiteResult:
    """测试套件结果"""
    suite_id: str
    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    results: List[TestResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration: float = 0.0
    
    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total * 100) if self.total > 0 else 0.0
    
    @property
    def is_acceptable(self) -> bool:
        return self.pass_rate >= 80.0 and self.errors == 0


@dataclass
class AuditRule:
    """审核规则"""
    id: str
    name: str
    description: str
    condition: str  # 规则表达式
    action: str  # block, warn, log
    severity: Severity = Severity.MEDIUM


@dataclass
class AuditResult:
    """审核结果"""
    audit_id: str
    timestamp: datetime
    status: SystemStatus
    violations: List[Issue] = field(default_factory=list)
    warnings: List[Issue] = field(default_factory=list)
    passed_checks: int = 0
    total_checks: int = 0
    test_results: Optional[TestSuiteResult] = None
    analysis_report: Optional[AnalysisReport] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_approved(self) -> bool:
        return (
            self.status == SystemStatus.PASSED and 
            len([v for v in self.violations if v.severity in (Severity.CRITICAL, Severity.HIGH)]) == 0
        )
    
    @property
    def block_count(self) -> int:
        return len([v for v in self.violations if v.severity in (Severity.CRITICAL, Severity.HIGH)])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": [w.to_dict() for w in self.warnings],
            "passed_checks": self.passed_checks,
            "total_checks": self.total_checks,
            "block_count": self.block_count,
            "is_approved": self.is_approved,
            "metadata": self.metadata,
        }
    
    def save(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


@dataclass
class LoopState:
    """闭环状态"""
    iteration: int
    current_phase: SystemStatus
    previous_phase: Optional[SystemStatus] = None
    analysis_report: Optional[AnalysisReport] = None
    test_results: Optional[TestSuiteResult] = None
    audit_results: List[AuditResult] = field(default_factory=list)
    issues_found: List[Issue] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries
    
    def increment_retry(self):
        self.retry_count += 1
