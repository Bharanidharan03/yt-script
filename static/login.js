// static/login.js

// Firebase Config (replace with your actual config)
const firebaseConfig = {
    apiKey: "AIzaSyCdu6NH9m4HMr5D52GDRfV-glXkYoNy248",
    authDomain: "foodie-fast.firebaseapp.com",
    projectId: "foodie-fast",
    storageBucket: "foodie-fast.appspot.com",
    messagingSenderId: "691200073660",
    appId: "1:691200073660:web:b7b079bd88b1d58d3e55b9",
    measurementId: "G-CHE6V7KGY5"
};

// Firebase Config


// Initialize Firebase
firebase.initializeApp(firebaseConfig);

// Google Sign-In
function loginWithGoogle() {
    const provider = new firebase.auth.GoogleAuthProvider();
    firebase.auth().signInWithPopup(provider)
        .then(result => result.user.getIdToken())
        .then(idToken => {
            return fetch('/sessionLogin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idToken })
            });
        })
        .then(response => {
            if (response.ok) window.location.href = "/hub";
            else throw new Error('Login failed');
        })
        .catch(error => {
            console.error('Google Sign-In Error:', error);
            document.getElementById('error-message').textContent = 'Google login failed';
        });
}

// Email/Password Sign-In
function loginWithEmailPassword() {
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;

    if (!email || !password) {
        document.getElementById('error-message').textContent = 'Please enter both email and password.';
        return;
    }

    firebase.auth().signInWithEmailAndPassword(email, password)
        .then(result => result.user.getIdToken())
        .then(idToken => {
            return fetch('/sessionLogin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idToken })
            });
        })
        .then(response => {
            if (response.ok) window.location.href = "/hub";
            else throw new Error('Login failed');
        })
        .catch(error => {
            console.error('Email Login Error:', error);
            document.getElementById('error-message').textContent = 'Invalid email or password.';
        });
}
