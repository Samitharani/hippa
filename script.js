let selectedRole = "doctor";

document.querySelectorAll(".role").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".role").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    selectedRole = btn.dataset.role;
  });
});

function login() {
  let user = document.getElementById("username").value.trim();
  let pass = document.getElementById("password").value.trim();
  let error = document.getElementById("error");

  if (!user || !pass) {
    error.innerText = "Username and password are required.";
    return;
  }

  error.innerText = "";

  fetch("http://127.0.0.1:8000/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      username: user,
      password: pass,
      role: selectedRole
    })
  })
  .then(res => {
    if (!res.ok) throw new Error("Invalid credentials");
    return res.json();
  })
  .then(data => {
  
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("role", data.role);


  if (selectedRole === "doctor") window.location.href = "doctor.html";
  if (selectedRole === "nurse") window.location.href = "nurse.html";
  if (selectedRole === "admin") window.location.href = "admin.html";
})

  .catch(err => {
    error.innerText = "Login failed. Check credentials.";
  });
}
