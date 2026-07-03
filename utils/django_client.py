import requests
from django.conf import settings
from utils.logger import get_logger
from utils.exceptions import DjangoAPIError

logger = get_logger(__name__)


class DjangoAPIClient:
    """
    HTTP client for communicating with the MySlates Django backend.
    Uses SimpleJWT for authentication.
    """

    # Sync endpoints — for polling changes (Django → Firestore)
    SYNC_ENDPOINTS = {
        # Auth
        "users":              "/auth/sync/users/",
        "students":           "/auth/sync/students/",
        "teachers":           "/auth/sync/teachers/",
        "parents":            "/auth/sync/parents/",
        # Academics
        "schools":            "/academics/sync/schools/",
        "classes":            "/academics/sync/classes/",
        "subjects":           "/academics/sync/subjects/",
        "topics":             "/academics/sync/topics/",
        # Assignments
        "assignments":        "/assignments/sync/assignments/",
        "submissions":        "/assignments/sync/submissions/",
        # Attendance
        "attendance":         "/attendance/sync/",
        # Communication
        "announcements":      "/communication/sync/announcements/",
        "results":            "/communication/sync/results/",
        "notifications":      "/communication/sync/notifications/",
        # Gamification
        "achievements":       "/gamification/sync/achievements/",
        "games":              "/gamification/sync/games/",
        "multiplayer_games":  "/gamification/sync/multiplayer-games/",
        "avatar_sounds":      "/gamification/sync/avatar-sounds/",
        # Chat
        "chats":              "/chat/sync/chats/",
        "communications":     "/chat/sync/communications/",
        "discussions":        "/chat/sync/discussions/",
        "messages":           "/chat/sync/messages/",
        # Modules
        "fees":               "/modules/sync/fees/",
        "subscriptions":      "/modules/sync/subscriptions/",
        "cbt_exams":          "/modules/sync/cbt-exams/",
        "practice_quizzes":   "/modules/sync/practice-quizzes/",
        "mock_results":       "/modules/sync/mock-results/",
    }

    # Write endpoints — for client → Django sync (kept for future use)
    CREATE_ENDPOINTS = {
        "schools":       "/academics/schools/create/",
        "classes":       "/academics/classes/create/",
        "subjects":      "/academics/subjects/create/",
        "topics":        "/academics/topics/create/",
        "assignments":   "/assignments/create/",
        "submissions":   "/assignments/submissions/create/",
        "attendance":    "/attendance/create/",
        "chats":         "/chat/chats/create/",
        "messages":      "/chat/messages/create/",
        "discussions":   "/chat/discussions/create/",
        "announcements": "/communication/announcements/create/",
        "results":       "/communication/results/create/",
        "notifications": "/communication/notifications/create/",
        "games":         "/gamification/games/create/",
        "fees":          "/modules/fees/create/",
        "cbt_exams":     "/modules/cbt-exams/create/",
    }

    BASE_ENDPOINTS = {
        "schools":       "/academics/schools/",
        "classes":       "/academics/classes/",
        "subjects":      "/academics/subjects/",
        "topics":        "/academics/topics/",
        "assignments":   "/assignments/",
        "submissions":   "/assignments/submissions/",
        "attendance":    "/attendance/",
        "users":         "/auth/users/",
        "students":      "/auth/students/",
        "teachers":      "/auth/teachers/",
        "parents":       "/auth/parents/",
        "chats":         "/chat/chats/",
        "messages":      "/chat/messages/",
        "discussions":   "/chat/discussions/",
        "announcements": "/communication/announcements/",
        "results":       "/communication/results/",
        "notifications": "/communication/notifications/",
        "achievements":  "/gamification/achievements/",
        "games":         "/gamification/games/",
        "fees":          "/modules/fees/",
        "cbt_exams":     "/modules/cbt-exams/",
        "video_classes": "/modules/video-classes/",
    }

    def __init__(self, access_token: str = None):
        self.base_url = settings.DJANGO_API_BASE_URL
        self.session  = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        if access_token:
            self.session.headers.update({
                "Authorization": f"Bearer {access_token}"
            })

    @classmethod
    def authenticate(cls, email: str, password: str) -> "DjangoAPIClient":
        base_url = settings.DJANGO_API_BASE_URL
        res = requests.post(
            f"{base_url}/auth/login/",
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json"},
        )

        if not res.ok:
            raise DjangoAPIError(f"Login failed [{res.status_code}]: {res.text}")

        data         = res.json()
        access_token = data.get("access")
        if not access_token:
            raise DjangoAPIError("Login response missing access token")

        logger.info("Successfully authenticated with MySlates backend")
        return cls(access_token=access_token)

    @classmethod
    def from_settings(cls) -> "DjangoAPIClient":
        return cls.authenticate(
            email    = settings.MYSLATES_SERVICE_EMAIL,
            password = settings.MYSLATES_SERVICE_PASSWORD,
        )

    def get_changes(self, collection: str, updated_after: str = None):
        """
        Poll a sync endpoint for records changed since updated_after.
        Returns a list of records.
        """
        path = self.SYNC_ENDPOINTS.get(collection)
        if not path:
            raise DjangoAPIError(f"No sync endpoint for collection: {collection}")

        url    = f"{self.base_url}{path}"
        params = {}
        if updated_after:
            params["updated_after"] = updated_after

        res = self.session.get(url, params=params)
        self._raise_for_status(res, "POLL", collection)

        data = res.json()
        # Handle both paginated and non-paginated responses
        if isinstance(data, dict):
            return data.get("results", [])
        return data

    def create(self, collection: str, payload: dict) -> dict:
        path = self.CREATE_ENDPOINTS.get(collection)
        if not path:
            raise DjangoAPIError(f"No create endpoint for collection: {collection}")
        url = f"{self.base_url}{path}"
        res = self.session.post(url, json=payload)
        self._raise_for_status(res, "CREATE", collection)
        return res.json()

    def update(self, collection: str, pk: str, payload: dict) -> dict:
        base = self.BASE_ENDPOINTS.get(collection)
        if not base:
            raise DjangoAPIError(f"Unknown collection: {collection}")
        url = f"{self.base_url}{base}{pk}/update/"
        res = self.session.patch(url, json=payload)
        self._raise_for_status(res, "UPDATE", collection)
        return res.json()

    def delete(self, collection: str, pk: str) -> None:
        base = self.BASE_ENDPOINTS.get(collection)
        if not base:
            raise DjangoAPIError(f"Unknown collection: {collection}")
        url = f"{self.base_url}{base}{pk}/delete/"
        res = self.session.delete(url)
        self._raise_for_status(res, "DELETE", collection)

    def get(self, collection: str, pk: str) -> dict:
        base = self.BASE_ENDPOINTS.get(collection)
        if not base:
            raise DjangoAPIError(f"Unknown collection: {collection}")
        url = f"{self.base_url}{base}{pk}/"
        res = self.session.get(url)
        self._raise_for_status(res, "GET", collection)
        return res.json()

    def _raise_for_status(self, response, method: str, collection: str):
        if not response.ok:
            msg = f"{method} {collection} failed [{response.status_code}]: {response.text}"
            logger.error(msg)
            raise DjangoAPIError(msg)