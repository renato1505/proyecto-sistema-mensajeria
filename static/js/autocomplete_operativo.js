function crearAutocomplete(input, options) {
    const lista = input.parentElement.querySelector(".autocomplete-list");
    if (!lista) return;

    let indexActivo = -1;

    function limpiar() {
        lista.innerHTML = "";
        indexActivo = -1;
    }

    function items() {
        return Array.from(lista.querySelectorAll(".list-group-item"));
    }

    function marcar() {
        items().forEach((item, index) => {
            item.classList.toggle("active", index === indexActivo);
        });

        const activo = items()[indexActivo];
        if (activo) {
            activo.scrollIntoView({ block: "nearest" });
        }
    }

    function mover(direccion) {
        const resultados = items();
        if (!resultados.length) return;

        indexActivo += direccion;
        if (indexActivo >= resultados.length) indexActivo = 0;
        if (indexActivo < 0) indexActivo = resultados.length - 1;
        marcar();
    }

    input.addEventListener("keydown", function (event) {
        if (!items().length) return;

        if (event.key === "ArrowDown") {
            event.preventDefault();
            mover(1);
        }

        if (event.key === "ArrowUp") {
            event.preventDefault();
            mover(-1);
        }

        if (event.key === "Enter" && indexActivo >= 0) {
            event.preventDefault();
            items()[indexActivo].click();
        }

        if (event.key === "Escape") {
            limpiar();
        }
    });

    input.addEventListener("input", async function () {
        const texto = input.value.trim();
        if (texto.length < 2) {
            limpiar();
            return;
        }

        const response = await fetch(`${options.url}?q=${encodeURIComponent(texto)}`);
        const resultados = await response.json();
        lista.innerHTML = "";
        indexActivo = -1;

        resultados.forEach((resultado) => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "list-group-item list-group-item-action";
            item.textContent = options.label(resultado);
            item.addEventListener("click", function () {
                options.select(resultado);
                limpiar();
            });
            lista.appendChild(item);
        });
    });

    document.addEventListener("click", function (event) {
        if (!input.contains(event.target) && !lista.contains(event.target)) {
            limpiar();
        }
    });
}

function setValue(selector, value) {
    const element = selector ? document.querySelector(selector) : null;
    if (element) {
        element.value = value || "";
    }
}

function normalizarTelefonoChileInput(valor) {
    let telefono = String(valor || "").replace(/\D/g, "");
    if (telefono.startsWith("56") && telefono.length >= 10) {
        telefono = telefono.slice(2);
    }
    if (telefono.startsWith("0") && (telefono.length === 9 || telefono.length === 10)) {
        telefono = telefono.slice(1);
    }
    return telefono.slice(0, 9);
}

function inicializarTelefonosOperativos() {
    document.querySelectorAll("input[name$='telefono_destinatario']").forEach((input) => {
        input.addEventListener("input", function () {
            this.value = normalizarTelefonoChileInput(this.value);
        });
    });
}

function inicializarAutocompletadosOperativos() {
    inicializarTelefonosOperativos();

    document.querySelectorAll("[data-autocomplete='comunas']").forEach((input) => {
        crearAutocomplete(input, {
            url: "/buscar_comunas",
            label: (comuna) => comuna.nombre,
            select: (comuna) => {
                input.value = comuna.nombre || "";
                setValue(input.dataset.regionTarget, comuna.region);
            }
        });
    });

    document.querySelectorAll("[data-autocomplete='remitentes']").forEach((input) => {
        crearAutocomplete(input, {
            url: "/buscar_remitentes",
            label: (remitente) => remitente.nombre,
            select: (remitente) => {
                input.value = remitente.nombre || "";
                setValue(input.dataset.correoTarget, remitente.correo);
                setValue(input.dataset.divisionTarget, remitente.division);
                setValue(input.dataset.centroCostoTarget, remitente.centro_costo);
            }
        });
    });

    document.querySelectorAll("[data-autocomplete='destinatarios']").forEach((input) => {
        crearAutocomplete(input, {
            url: "/buscar_destinatarios",
            label: (destinatario) => destinatario.nombre,
            select: (destinatario) => {
                input.value = destinatario.nombre || "";
                setValue(input.dataset.rutTarget, destinatario.rut);
                setValue(input.dataset.direccionTarget, destinatario.direccion);
                setValue(input.dataset.comunaTarget, destinatario.comuna);
                setValue(input.dataset.regionTarget, destinatario.region);
                setValue(input.dataset.telefonoTarget, destinatario.telefono);
                setValue(input.dataset.correoTarget, destinatario.correo);
                setValue(input.dataset.observacionTarget, destinatario.observacion);
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", inicializarAutocompletadosOperativos);
