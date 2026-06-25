function abrirModalReporte(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.add("is-open");
        modal.setAttribute("aria-hidden", "false");
    }
}

function cerrarModalReporte(modal) {
    if (modal) {
        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");
    }
}

document.querySelectorAll("[data-modal-target]").forEach((button) => {
    button.addEventListener("click", () => abrirModalReporte(button.dataset.modalTarget));
});

document.querySelectorAll("[data-modal-close]").forEach((button) => {
    button.addEventListener("click", () => cerrarModalReporte(button.closest(".report-modal")));
});

document.querySelectorAll(".report-modal").forEach((modal) => {
    modal.addEventListener("click", (event) => {
        if (event.target === modal) cerrarModalReporte(modal);
    });
});

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        document.querySelectorAll(".report-modal.is-open").forEach(cerrarModalReporte);
    }
});

function crearAutocompleteReporte(inputId, listId, url, minLength) {
    const input = document.getElementById(inputId);
    const lista = document.getElementById(listId);
    if (!input || !lista) return;

    function limpiar() {
        lista.innerHTML = "";
    }

    input.addEventListener("input", async function() {
        const texto = this.value.trim();
        if (texto.length < minLength) {
            limpiar();
            return;
        }

        const response = await fetch(`${url}?q=${encodeURIComponent(texto)}`);
        const resultados = await response.json();
        lista.innerHTML = "";

        resultados.slice(0, 8).forEach((valor) => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "list-group-item list-group-item-action";
            item.textContent = valor;
            item.addEventListener("click", () => {
                input.value = valor;
                limpiar();
            });
            lista.appendChild(item);
        });
    });

    document.addEventListener("click", (event) => {
        if (!input.contains(event.target) && !lista.contains(event.target)) limpiar();
    });
}

crearAutocompleteReporte("reporte_of", "lista_reporte_of", "/buscar_of_historico", 1);
crearAutocompleteReporte("reporte_busqueda", "lista_reporte_busqueda", "/buscar_reportes_sugerencias", 1);

function abrirReporteDesdeHash() {
    const id = window.location.hash.replace("#", "");
    if (!id) return;

    const reporte = document.getElementById(id);
    if (!reporte) return;

    const grupo = reporte.closest(".report-group");
    const detalle = reporte.querySelector(".case-detail");

    if (grupo) grupo.open = true;
    if (detalle) detalle.open = true;

    window.setTimeout(() => {
        reporte.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 100);
}

window.addEventListener("load", abrirReporteDesdeHash);
window.addEventListener("hashchange", abrirReporteDesdeHash);
