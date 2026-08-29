document.addEventListener("DOMContentLoaded", function () {
    const storageKey = "mensajeria:retiros:seleccion";
    const todos = JSON.parse(document.getElementById("retirosTodosData")?.textContent || "[]");
    const filtrados = JSON.parse(document.getElementById("retirosFiltradosData")?.textContent || "[]");
    const checkboxes = Array.from(document.querySelectorAll(".retiro-checkbox"));
    const cantidad = document.getElementById("seleccionCantidad");
    const bultos = document.getElementById("seleccionBultos");
    const modalCantidad = document.getElementById("modalSeleccionCantidad");
    const modalBultos = document.getElementById("modalSeleccionBultos");
    const botonAbrir = document.getElementById("abrirConfirmacionRetiro");
    const botonSubmit = document.getElementById("confirmarRetiroSubmit");
    const idsContainer = document.getElementById("retiroIdsSeleccionados");
    const idsElegibles = new Set(todos.map(item => String(item.id)));
    let seleccion = {};

    try {
        seleccion = JSON.parse(sessionStorage.getItem(storageKey) || "{}") || {};
    } catch (_error) {
        seleccion = {};
    }

    Object.keys(seleccion).forEach(function (id) {
        if (!idsElegibles.has(id)) delete seleccion[id];
    });

    function guardar() {
        sessionStorage.setItem(storageKey, JSON.stringify(seleccion));
    }

    function renderizar() {
        const ids = Object.keys(seleccion);
        const totalBultos = ids.reduce((total, id) => total + Number(seleccion[id] || 0), 0);
        checkboxes.forEach(function (checkbox) {
            checkbox.checked = Object.prototype.hasOwnProperty.call(seleccion, checkbox.dataset.envioId);
        });
        [cantidad, modalCantidad].forEach(elemento => { if (elemento) elemento.textContent = String(ids.length); });
        [bultos, modalBultos].forEach(elemento => { if (elemento) elemento.textContent = String(totalBultos); });
        if (botonAbrir) botonAbrir.disabled = ids.length === 0;
        if (botonSubmit) botonSubmit.disabled = ids.length === 0;
        if (idsContainer) {
            idsContainer.replaceChildren(...ids.map(function (id) {
                const input = document.createElement("input");
                input.type = "hidden";
                input.name = "envio_ids";
                input.value = id;
                return input;
            }));
        }
        guardar();
    }

    checkboxes.forEach(function (checkbox) {
        checkbox.addEventListener("change", function () {
            const id = checkbox.dataset.envioId;
            if (checkbox.checked) seleccion[id] = Number(checkbox.dataset.bultos || 0);
            else delete seleccion[id];
            renderizar();
        });
    });

    document.getElementById("seleccionarResultados")?.addEventListener("click", function () {
        filtrados.forEach(item => { seleccion[String(item.id)] = Number(item.bultos || 0); });
        renderizar();
    });

    document.getElementById("limpiarSeleccion")?.addEventListener("click", function () {
        seleccion = {};
        renderizar();
    });

    renderizar();
});
