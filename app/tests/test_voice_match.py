import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.services.tts_voice_features import extract_audio_features
from app.services.supabase_service import supabase

# 녹음 목소리 feature
my_vec = extract_audio_features("recorded_voice.wav").reshape(1, -1)

# 2️⃣ DB voice들 가져오기
voices = (
    supabase
    .table("tts_voice")
    .select("id, name, feature_vector")
    .execute()
    .data
)

results = []

for v in voices:
    vec = np.array(v["feature_vector"]).reshape(1, -1)
    sim = cosine_similarity(my_vec, vec)[0][0]
    results.append((v["name"], sim))

# 3️⃣ 정렬
results.sort(key=lambda x: x[1], reverse=True)

for name, score in results[:5]:
    print(f"{name}: {score:.4f}")
