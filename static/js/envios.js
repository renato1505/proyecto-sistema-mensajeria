document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("formGenerarCsv");
    const estado = document.getElementById("estadoDescargaCsv");
    const btnDescargar = document.getElementById("btnDescargarCsv");
    const btnEnviar = document.getElementById("btnEnviarCsv");
    const selectores = Array.from(document.querySelectorAll(".envio-selector"));
    const seleccionarTodos = document.getElementById("seleccionarTodosVisibles");
    const limpiarSeleccion = document.getElementById("limpiarSeleccion");
    const abrirGenerarLote = document.getElementById("abrirGenerarLote");
    const seleccionCantidad = document.getElementById("seleccionCantidad");
    const seleccionBultos = document.getElementById("seleccionBultos");
    const seleccionKilos = document.getElementById("seleccionKilos");
    const modalSeleccionCantidad = document.getElementById("modalSeleccionCantidad");

    if (!form) {
        return;
    }

    function numeroSeguro(valor) {
        const numero = Number.parseFloat(valor);
        return Number.isFinite(numero) ? numero : 0;
    }

    function formatearNumero(numero) {
        return new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 }).format(numero);
    }

    function actualizarSeleccion() {
        const seleccionados = selectores.filter(selector => selector.checked);
        const bultos = seleccionados.reduce((total, selector) => total + numeroSeguro(selector.dataset.bultos), 0);
        const kilos = seleccionados.reduce((total, selector) => total + numeroSeguro(selector.dataset.kilos), 0);
        const haySeleccion = seleccionados.length > 0;

        seleccionCantidad.textContent = String(seleccionados.length);
        seleccionBultos.textContent = formatearNumero(bultos);
        seleccionKilos.textContent = formatearNumero(kilos);
        modalSeleccionCantidad.textContent = String(seleccionados.length);
        abrirGenerarLote.disabled = !haySeleccion;
        limpiarSeleccion.disabled = !haySeleccion;

        if (seleccionarTodos) {
            seleccionarTodos.checked = selectores.length > 0 && seleccionados.length === selectores.length;
            seleccionarTodos.indeterminate = seleccionados.length > 0 && seleccionados.length < selectores.length;
        }
    }

    selectores.forEach(selector => selector.addEventListener("change", actualizarSeleccion));

    if (seleccionarTodos) {
        seleccionarTodos.addEventListener("change", function () {
            selectores.forEach(selector => {
                selector.checked = seleccionarTodos.checked;
            });
            actualizarSeleccion();
        });
    }

    if (limpiarSeleccion) {
        limpiarSeleccion.addEventListener("click", function () {
            selectores.forEach(selector => {
                selector.checked = false;
            });
            actualizarSeleccion();
        });
    }

    actualizarSeleccion();

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
