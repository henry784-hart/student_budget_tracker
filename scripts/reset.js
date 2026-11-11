// Reset password page: reads ?token=... from the emailed link and sets a new password.
const API_URL =
  location.hostname === "localhost" || location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:5000/api"
    : "https://student-budget-api.onrender.com/api";

const MIN_PASSWORD_LEN = 8;

const resetForm = document.getElementById("reset-form");
const passwordInput = document.getElementById("password");
const confirmInput = document.getElementById("confirm");
const submitBtn = document.getElementById("submit-btn");
const messageEl = document.getElementById("auth-message");

const token = new URLSearchParams(location.search).get("token") || "";

function showMessage(text, isSuccess = false) {
  messageEl.textContent = text;
  messageEl.classList.toggle("success", isSuccess);
  messageEl.style.display = text ? "block" : "none";
}

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

async function submit(event) {
  event.preventDefault();

  const password = passwordInput.value;
  if (password.length < MIN_PASSWORD_LEN) {
    showMessage(`Password must be at least ${MIN_PASSWORD_LEN} characters.`);
    return;
  }
  if (password !== confirmInput.value) {
    showMessage("The two passwords do not match.");
    return;
  }

  submitBtn.disabled = true;
  try {
    const data = await request("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    });
    showMessage(data.message + " Taking you to sign in…", true);
    resetForm.style.display = "none";
    setTimeout(() => location.replace("login.html"), 1800);
  } catch (err) {
    showMessage(describeError(err));
    submitBtn.disabled = false;
  }
}

if (!token) {
  showMessage("This page needs the link from your reset email. Go back and request a new one.");
  submitBtn.disabled = true;
  resetForm.style.display = "none";
} else {
  resetForm.addEventListener("submit", submit);
  passwordInput.focus();
}
