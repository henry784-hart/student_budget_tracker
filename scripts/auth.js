// 1. Settings
// Locally the API runs on port 5000; on GitHub Pages it points at the deployed backend.
const API_URL =
  location.hostname === "localhost" || location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:5000/api"
    : "https://student-budget-tracker-api.onrender.com/api";

const MIN_PASSWORD_LEN = 8;

// 2. Elements
const authForm = document.getElementById("auth-form");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const confirmInput = document.getElementById("confirm");
const confirmField = document.getElementById("confirm-field");
const passwordHint = document.getElementById("password-hint");
const submitBtn = document.getElementById("submit-btn");
const messageEl = document.getElementById("auth-message");
const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const forgotRow = document.getElementById("forgot-row");
const forgotBtn = document.getElementById("forgot-btn");

let mode = "login";

// 3. UI helpers
function showMessage(text, isSuccess = false) {
  messageEl.textContent = text;
  messageEl.classList.toggle("success", isSuccess);
  messageEl.style.display = text ? "block" : "none";
}

function setMode(next) {
  mode = next;
  const isLogin = mode === "login";

  tabLogin.classList.toggle("is-active", isLogin);
  tabRegister.classList.toggle("is-active", !isLogin);

  submitBtn.textContent = isLogin ? "Sign in" : "Create account";
  submitBtn.dataset.mode = mode;
  passwordInput.autocomplete = isLogin ? "current-password" : "new-password";
  confirmField.style.display = isLogin ? "none" : "block";
  passwordHint.style.display = isLogin ? "none" : "block";
  forgotRow.style.display = isLogin ? "block" : "none";

  showMessage("");
}

// 4. Talking to the server
async function request(path, options = {}) {
  const response = await fetch(API_URL + path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Something went wrong.");
  }
  return data;
}

function describeError(err) {
  if (err instanceof TypeError) {
    return "Cannot reach the server. Is the backend running on port 5000?";
  }
  return err.message;
}

// Send people who are already signed in straight to the tracker.
async function goToAppIfSignedIn() {
  try {
    await request("/auth/me");
    location.replace("index.html");
  } catch (err) {
    // Not signed in: stay on this page.
  }
}

// 5. Submit
async function submit(event) {
  event.preventDefault();

  const email = emailInput.value.trim();
  const password = passwordInput.value;

  if (!email || !password) {
    showMessage("Enter your email and password.");
    return;
  }

  if (mode === "register") {
    if (password.length < MIN_PASSWORD_LEN) {
      showMessage(`Password must be at least ${MIN_PASSWORD_LEN} characters.`);
      return;
    }
    if (password !== confirmInput.value) {
      showMessage("The two passwords do not match.");
      return;
    }
  }

  submitBtn.disabled = true;
  try {
    if (mode === "login") {
      await request("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
    } else {
      await request("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
    }
    showMessage("Signed in. Taking you to your tracker…", true);
    location.replace("index.html");
  } catch (err) {
    showMessage(describeError(err));
    passwordInput.value = "";
    confirmInput.value = "";
    passwordInput.focus();
  } finally {
    submitBtn.disabled = false;
  }
}

// 5b. Forgot password: email the account owner a one-hour reset link.
async function forgotPassword() {
  const email = emailInput.value.trim();
  if (!email) {
    showMessage("Type your email above first, then tap \"Forgot your password?\".");
    emailInput.focus();
    return;
  }

  forgotBtn.disabled = true;
  try {
    const data = await request("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    let message = data.message || "Check your email for a reset link.";
    // Only present in local development (server opt-in).
    if (data.reset_link) {
      message += " Development link: " + data.reset_link;
    }
    showMessage(message, true);
  } catch (err) {
    showMessage(describeError(err));
  } finally {
    forgotBtn.disabled = false;
  }
}

// 6. Wire it up
tabLogin.addEventListener("click", () => setMode("login"));
tabRegister.addEventListener("click", () => setMode("register"));
authForm.addEventListener("submit", submit);
forgotBtn.addEventListener("click", forgotPassword);

setMode("login");
goToAppIfSignedIn();
emailInput.focus();
