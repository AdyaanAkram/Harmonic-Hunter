from pydantic import BaseModel

class Settings(BaseModel):
    fundamental_hz: float = 60.0
    harmonics: tuple[int, ...] = (1, 3, 5, 7, 9, 11, 13)

    # If your samples are irregular, we resample at this interval (seconds)
    resample_seconds: float = 1.0

    # Defaults used if not present in CSV
    default_phase: str = "A"

settings = Settings()
