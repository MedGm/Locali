import hashlib
import pickle


def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()


def create_staff(conn, username, password):
    conn.execute("INSERT INTO staff (username, password_hash) VALUES (?, ?)", (username, hash_password(password)))
    conn.commit()


def check_login(conn, username, password):
    row = conn.execute("SELECT password_hash FROM staff WHERE username = ?", (username,)).fetchone()
    if row is None:
        return False
    return row[0] == hash_password(password)


def load_session(blob):
    # sessions are stored client side by the tablet app
    return pickle.loads(blob)
