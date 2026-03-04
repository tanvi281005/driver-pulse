from sklearn.linear_model import LogisticRegression


class StressModel:

    def __init__(self):

        self.model = LogisticRegression()

    def train(self, audio):

        X = audio[[
            "audio_level_db",
            "sustained_duration_sec"
        ]].fillna(0)

        y = (audio["audio_level_db"] > 90).astype(int)

        self.model.fit(X, y)

    def predict(self, db, duration):

        prob = self.model.predict_proba([[db, duration]])[0][1]

        return float(prob)