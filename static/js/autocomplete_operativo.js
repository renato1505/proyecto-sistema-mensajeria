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

const CODIGOS_TELEFONO_OPERATIVO = ["598", "56", "54", "51", "57", "52", "55", "1"];

function normalizarTelefonoOperativoInput(valor, codigoPais = "56", selectCodigo = null) {
    const texto = String(valor || "").trim();
    let telefono = texto.replace(/\D/g, "");

    if (texto.startsWith("+")) {
        const codigoDetectado = CODIGOS_TELEFONO_OPERATIVO.find((codigo) => telefono.startsWith(codigo));
        if (codigoDetectado) {
            if (selectCodigo) selectCodigo.value = codigoDetectado;
            codigoPais = codigoDetectado;
            telefono = telefono.slice(codigoDetectado.length);
        }
    }

    if (codigoPais !== "56") {
        if (telefono.startsWith(codigoPais)) {
            telefono = telefono.slice(codigoPais.length);
        }
        if (telefono.startsWith("0")) {
            telefono = telefono.slice(1);
        }
        return telefono.slice(0, 15);
    }

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
        const group = input.closest(".input-group");
        const selectCodigo = group ? group.querySelector("select[name='telefono_codigo_pais']") : null;

        input.addEventListener("input", function () {
            this.value = normalizarTelefonoOperativoInput(
                this.value,
                selectCodigo?.value || "56",
                selectCodigo
            );
        });

        if (selectCodigo) {
            selectCodigo.addEventListener("change", function () {
                input.value = normalizarTelefonoOperativoInput(input.value, this.value, this);
            });
        }
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
                const telefonoInput = input.dataset.telefonoTarget
                    ? document.querySelector(input.dataset.telefonoTarget)
                    : null;
                const telefonoGroup = telefonoInput ? telefonoInput.closest(".input-group") : null;
                const selectCodigo = telefonoGroup
                    ? telefonoGroup.querySelector("select[name='telefono_codigo_pais']")
                    : null;
                if (telefonoInput) {
                    telefonoInput.value = normalizarTelefonoOperativoInput(
                        destinatario.telefono,
                        selectCodigo?.value || "56",
                        selectCodigo
                    );
                }
                setValue(input.dataset.correoTarget, destinatario.correo);
                setValue(input.dataset.observacionTarget, destinatario.observacion);
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", inicializarAutocompletadosOperativos);
