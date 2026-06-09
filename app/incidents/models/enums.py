import enum


class NotificationType(str, enum.Enum):
    NEW_REQUEST = "new_request"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    STATUS_UPDATE = "status_update"
    PAYMENT = "payment"
    SYSTEM = "system"
    SERVICE_COMPLETED = "service_completed"


class PaymentMethod(str, enum.Enum):
    QR = "qr"
    CARD = "card"
    CASH = "cash"
    TRANSFER = "transfer"
    PAYPAL = "paypal"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class IncidentStatus(str, enum.Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    PENDING_INFO = "pending_info"
    MATCHED = "matched"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_OFFERS = "no_offers"
    ERROR = "error"


class IncidentPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EvidenceType(str, enum.Enum):
    IMAGE = "image"
    AUDIO = "audio"
    TEXT = "text"


class OfferStatus(str, enum.Enum):
    NOTIFIED = "notified"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    EXPIRED = "expired"


class RejectionReason(str, enum.Enum):
    NO_REASON = "no_reason"
    BUSY = "busy"
    FAR_FROM_ZONE = "far_from_zone"
    NO_PARTS = "no_parts"
    NO_TECHNICIAN = "no_technician"
    TIMEOUT_NO_RESPONSE = "timeout_no_response"
