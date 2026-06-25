(function () {
    const usuario = document.getElementById("usuario");
    const recordar = document.getElementById("recordarUsuario");
    const form = document.getElementById("loginForm");
    const guardado = window.localStorage.getItem("portal_usuario_recordado");

    if (guardado && usuario && recordar) {
        usuario.value = guardado;
        recordar.checked = true;
        document.getElementById("clave")?.focus();
    }

    form?.addEventListener("submit", function () {
        if (!usuario || !recordar) return;
        if (recordar.checked) {
            window.localStorage.setItem("portal_usuario_recordado", usuario.value.trim().toLowerCase());
        } else {
            window.localStorage.removeItem("portal_usuario_recordado");
        }
    });

    document.getElementById("togglePassword")?.addEventListener("click", function () {
        const clave = document.getElementById("clave");
        if (!clave) return;
        clave.type = clave.type === "password" ? "text" : "password";
    });

    const recovery = document.getElementById("recoveryModal");
    const recoveryForm = document.getElementById("recoveryForm");

    document.getElementById("openRecovery")?.addEventListener("click", function () {
        if (recovery) {
            recovery.hidden = false;
            recoveryForm?.querySelector("input[name='usuario_recuperacion']")?.focus();
        }
    });

    function cerrarRecuperacion() {
        if (recovery) recovery.hidden = true;
    }

    document.getElementById("closeRecovery")?.addEventListener("click", cerrarRecuperacion);
    document.querySelector("[data-close-recovery]")?.addEventListener("click", cerrarRecuperacion);
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") cerrarRecuperacion();
    });
})();
