import pandas as pd
import numpy as np
#from sklearn.metrics.pairwise import cosine_similarity
#from sklearn.feature_extraction.text import CountVectorizer
import re
from collections import defaultdict
from scipy.sparse import csr_matrix

df = pd.read_csv(r'store/Books.csv', encoding='utf-8', dtype={'Year-Of-Publication': 'str'}, low_memory=False)

combined_df = pd.concat([df], ignore_index=True)
combined_df.columns = combined_df.columns.str.strip()


def cosine_similarity(matrix, vector):
    dot_products = matrix.dot(vector.T).toarray().flatten()
    matrix_norms = np.linalg.norm(matrix.toarray(), axis=1)
    vector_norm = np.linalg.norm(vector.toarray())
    similarities = dot_products / (matrix_norms * vector_norm + 1e-10)  # Add small value to avoid division by zero
    return similarities
    

# Custom CountVectorizer implementation
class CountVectorizer:
    def __init__(self):
        self.vocabulary_ = {}

    def _tokenize(self, text):
        # Basic tokenizer: lowercase and split on non-word characters
        return re.findall(r'\b\w+\b', text.lower())

    def fit(self, texts):
        vocab = set()
        for text in texts:
            tokens = self._tokenize(text)
            vocab.update(tokens)
        self.vocabulary_ = {word: idx for idx, word in enumerate(sorted(vocab))}

    def transform(self, texts):
        rows = []
        cols = []
        data = []

        for row_idx, text in enumerate(texts):
            token_counts = defaultdict(int)
            tokens = self._tokenize(text)
            for token in tokens:
                if token in self.vocabulary_:
                    token_counts[self.vocabulary_[token]] += 1
            for col_idx, count in token_counts.items():
                rows.append(row_idx)
                cols.append(col_idx)
                data.append(count)

        return csr_matrix((data, (rows, cols)), shape=(len(texts), len(self.vocabulary_)))

    def fit_transform(self, texts):
        self.fit(texts)
        return self.transform(texts)


def recommend(db_books_df, book_title):
    if book_title not in db_books_df['name'].values:
        return []

    db_books_df['combined'] = db_books_df[['name', 'author', 'publication']].apply(lambda x: ' '.join(str(i) for i in x), axis=1)

    vectorizer = CountVectorizer()
    vectors = vectorizer.fit_transform(db_books_df['combined'])

    db_index = db_books_df[db_books_df['name'] == book_title].index[0]
    db_vector = vectorizer.transform([db_books_df.loc[db_index, 'combined']])
    similarity_scores = cosine_similarity(db_vector, vectors).flatten()
    print(similarity_scores)
    top_matches = similarity_scores.argsort()[-6:-1][::-1]
    recommended_books = db_books_df.iloc[top_matches]['name'].tolist()

    return recommended_books