document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("formGenerarCsv");
    const estado = document.getElementById("estadoDescargaCsv");
    const btnDescargar = document.getElementById("btnDescargarCsv");
    const btnEnviar = document.getElementById("btnEnviarCsv");

    if (!form) {
        return;
    }

    form.addEventListener("submit", async function (event) {
        const accion = event.submitter ? event.submitter.value : "";

        if (accion !== "descargar") {
            return;
        }

        event.preventDefault();
        btnDescargar.disabled = true;
        btnEnviar.disabled = true;
        btnDescargar.textContent = "Descargando...";

        const formData = new FormData(form);
        formData.set("accion", "descargar");

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: formData,
                credentials: "same-origin"
            });

            const contentType = response.headers.get("content-type") || "";
            if (!response.ok || contentType.includes("text/html")) {
                window.location.href = "/envios";
                return;
            }

            const blob = await response.blob();
            const disposition = response.headers.get("content-disposition") || "";
            const match = disposition.match(/filename="?([^"]+)"?/i);
            const filename = match ? match[1] : "starken.csv";
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement("a");

            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);

            if (estado) {
                estado.classList.remove("d-none");
            }

            setTimeout(function () {
                window.location.href = "/en_proceso";
            }, 1200);
        } catch (error) {
            window.location.href = "/envios";
        }
    });
});
