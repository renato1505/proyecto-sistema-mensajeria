const tipoEnvio = document.getElementById("tipo_envio");
const bloqueAgencia = document.getElementById("bloque_agencia");
const codigoAgencia = document.getElementById("codigo_agencia");

const inputComuna = document.getElementById("comuna");
const inputRegion = document.getElementById("region");
const listaComunas = document.getElementById("lista_comunas");

const inputRemitente = document.getElementById("remitente");
const inputCorreoRemitente = document.getElementById("correo_remitente");
const inputDivision = document.getElementById("division");
const inputCentroCosto = document.getElementById("centro_costo");
const listaRemitentes = document.getElementById("lista_remitentes");

const inputDestinatario = document.getElementById("destinatario");
const inputRutDestinatario = document.getElementById("rut_destinatario");
const inputDireccion = document.getElementById("direccion");
const inputComun = document.getElementById("comuna");
const inputRegio = document.getElementById("region");
const inputTelefonoDestinatario = document.getElementById("telefono_destinatario");
const listaDestinatarios = document.getElementById("lista_destinatarios");

const inputBultos = document.getElementById("bultos");
const inputKilos = document.getElementById("kilos");
const switchMantenerRemitente = document.getElementById("mantener_remitente");

const autocompleteState = {
    comunas: { index: -1 },
    remitentes: { index: -1 },
    destinatarios: { index: -1 }
};

const STORAGE_KEY = "nuevo_envio_remitente";
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

function limpiarLista(lista, stateKey) {
    lista.innerHTML = "";
    autocompleteState[stateKey].index = -1;
}

function obtenerItemsLista(lista) {
    return Array.from(lista.querySelectorAll(".list-group-item"));
}

function marcarItemActivo(lista, stateKey) {
    const items = obtenerItemsLista(lista);
    items.forEach((item, i) => {
        item.classList.toggle("active", i === autocompleteState[stateKey].index);
    });

    const activo = items[autocompleteState[stateKey].index];
    if (activo) {
        activo.scrollIntoView({ block: "nearest" });
    }
}

function moverSeleccion(lista, stateKey, direccion) {
    const items = obtenerItemsLista(lista);
    if (!items.length) return;

    if (direccion === "down") {
        autocompleteState[stateKey].index++;
        if (autocompleteState[stateKey].index >= items.length) {
            autocompleteState[stateKey].index = 0;
        }
    } else if (direccion === "up") {
        autocompleteState[stateKey].index--;
        if (autocompleteState[stateKey].index < 0) {
            autocompleteState[stateKey].index = items.length - 1;
        }
    }

    marcarItemActivo(lista, stateKey);
}

function seleccionarActivo(lista, stateKey) {
    const items = obtenerItemsLista(lista);
    const activo = items[autocompleteState[stateKey].index];
    if (activo) {
        activo.click();
        return true;
    }
    return false;
}

function manejarTecladoAutocomplete(event, lista, stateKey) {
    const items = obtenerItemsLista(lista);
    if (!items.length) return;

    if (event.key === "ArrowDown") {
        event.preventDefault();
        moverSeleccion(lista, stateKey, "down");
    }

    if (event.key === "ArrowUp") {
        event.preventDefault();
        moverSeleccion(lista, stateKey, "up");
    }

    if (event.key === "Enter") {
        if (autocompleteState[stateKey].index >= 0) {
            event.preventDefault();
            seleccionarActivo(lista, stateKey);
        }
    }

    if (event.key === "Escape") {
        limpiarLista(lista, stateKey);
    }
}

function obtenerDatosRemitente() {
    return {
        remitente: inputRemitente.value.trim(),
        correo_remitente: inputCorreoRemitente.value.trim(),
        division: inputDivision.value.trim(),
        centro_costo: inputCentroCosto.value.trim()
    };
}

function guardarRemitenteEnStorage() {
    if (!switchMantenerRemitente) return;

    if (switchMantenerRemitente.checked) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(obtenerDatosRemitente()));
        localStorage.setItem("mantener_remitente_activo", "1");
    } else {
        localStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem("mantener_remitente_activo");
    }
}

function restaurarRemitenteDesdeStorage() {
    const activo = localStorage.getItem("mantener_remitente_activo");
    if (activo === "1" && switchMantenerRemitente) {
        switchMantenerRemitente.checked = true;

        const data = localStorage.getItem(STORAGE_KEY);
        if (data) {
            try {
                const remitente = JSON.parse(data);
                inputRemitente.value = remitente.remitente || "";
                inputCorreoRemitente.value = remitente.correo_remitente || "";
                inputDivision.value = remitente.division || "";
                inputCentroCosto.value = remitente.centro_costo || "";
            } catch (e) {
                localStorage.removeItem(STORAGE_KEY);
            }
        }
    }
}

function actualizarBloqueAgencia() {
    if (tipoEnvio.value === "Agencia") {
        bloqueAgencia.style.display = "block";
        codigoAgencia.required = true;
    } else {
        bloqueAgencia.style.display = "none";
        codigoAgencia.required = false;
        codigoAgencia.value = "";
    }
    actualizarPreview();
}

tipoEnvio.addEventListener("change", actualizarBloqueAgencia);
actualizarBloqueAgencia();

codigoAgencia.addEventListener("input", function () {
    this.value = this.value.replace(/\D/g, "").slice(0, 5);
    actualizarPreview();
});

inputTelefonoDestinatario.addEventListener("input", function () {
    let telefono = this.value.replace(/\D/g, "");
    if ((telefono.length === 10 || telefono.length === 11) && telefono.startsWith("56")) {
        telefono = telefono.slice(2);
    }
    this.value = telefono.slice(0, 9);
    actualizarPreview();
});

inputRutDestinatario.addEventListener("input", function () {
    this.value = this.value.replace(/[^0-9kK-]/g, "").slice(0, 10);
    actualizarPreview();
});

if (inputBultos) {
    inputBultos.addEventListener("input", function () {
        if (this.value.length > 4) {
            this.value = this.value.slice(0, 4);
        }
        actualizarPreview();
    });
}

if (inputKilos) {
    inputKilos.addEventListener("input", function () {
        if (this.value.length > 4) {
            this.value = this.value.slice(0, 4);
        }
        actualizarPreview();
    });
}

inputComuna.addEventListener("keydown", function (e) {
    manejarTecladoAutocomplete(e, listaComunas, "comunas");
});

inputComuna.addEventListener("input", async function () {
    const texto = this.value.trim();

    if (texto.length < 2) {
        limpiarLista(listaComunas, "comunas");
        actualizarPreview();
        return;
    }

    const response = await fetch(`/buscar_comunas?q=${encodeURIComponent(texto)}`);
    const comunas = await response.json();

    listaComunas.innerHTML = "";
    autocompleteState.comunas.index = -1;

    comunas.forEach(comuna => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "list-group-item list-group-item-action";
        item.textContent = comuna.nombre;

        item.addEventListener("click", function () {
            inputComuna.value = comuna.nombre;
            inputRegion.value = comuna.region;
            limpiarLista(listaComunas, "comunas");
            actualizarPreview();
        });

        listaComunas.appendChild(item);
    });
});

document.addEventListener("click", function (e) {
    if (!inputComuna.contains(e.target) && !listaComunas.contains(e.target)) {
        limpiarLista(listaComunas, "comunas");
    }
});

inputRemitente.addEventListener("keydown", function (e) {
    manejarTecladoAutocomplete(e, listaRemitentes, "remitentes");
});

inputRemitente.addEventListener("input", async function () {
    guardarRemitenteEnStorage();

    const texto = this.value.trim();

    if (texto.length < 2) {
        limpiarLista(listaRemitentes, "remitentes");
        actualizarPreview();
        return;
    }

    const response = await fetch(`/buscar_remitentes?q=${encodeURIComponent(texto)}`);
    const remitentes = await response.json();

    listaRemitentes.innerHTML = "";
    autocompleteState.remitentes.index = -1;

    remitentes.forEach(remitente => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "list-group-item list-group-item-action";
        item.textContent = remitente.nombre;

        item.addEventListener("click", function () {
            inputRemitente.value = remitente.nombre || "";
            inputCorreoRemitente.value = remitente.correo || "";
            inputDivision.value = remitente.division || "";
            inputCentroCosto.value = remitente.centro_costo || "";
            limpiarLista(listaRemitentes, "remitentes");
            guardarRemitenteEnStorage();
            actualizarPreview();
        });

        listaRemitentes.appendChild(item);
    });
});

document.addEventListener("click", function (e) {
    if (!inputRemitente.contains(e.target) && !listaRemitentes.contains(e.target)) {
        limpiarLista(listaRemitentes, "remitentes");
    }
});

async function guardarRemitente() {
    const remitente = document.getElementById("remitente").value.trim();
    const correo = document.getElementById("correo_remitente").value.trim();
    const division = document.getElementById("division").value.trim();
    const centroCosto = document.getElementById("centro_costo").value.trim();

    const formData = new FormData();
    formData.append("csrf_token", csrfToken);
    formData.append("remitente", remitente);
    formData.append("correo_remitente", correo);
    formData.append("division", division);
    formData.append("centro_costo", centroCosto);

    const response = await fetch("/guardar_remitente", {
        method: "POST",
        body: formData
    });

    const resultado = await response.json();
    alert(resultado.mensaje);
    actualizarPreview();
}

async function guardarDestinatario() {
    const destinatario = document.getElementById("destinatario").value.trim();
    const rut = document.getElementById("rut_destinatario").value.trim();
    const direccion = document.getElementById("direccion").value.trim();
    const comuna = document.getElementById("comuna").value.trim();
    const region = document.getElementById("region").value.trim();
    const telefono = document.getElementById("telefono_destinatario").value.trim();

    const formData = new FormData();
    formData.append("csrf_token", csrfToken);
    formData.append("destinatario", destinatario);
    formData.append("rut_destinatario", rut);
    formData.append("direccion", direccion);
    formData.append("comuna", comuna);
    formData.append("region", region);
    formData.append("telefono_destinatario", telefono);

    const response = await fetch("/guardar_destinatario", {
        method: "POST",
        body: formData
    });

    const resultado = await response.json();
    alert(resultado.mensaje);
    actualizarPreview();
}

inputDestinatario.addEventListener("keydown", function (e) {
    manejarTecladoAutocomplete(e, listaDestinatarios, "destinatarios");
});

inputDestinatario.addEventListener("input", async function () {
    const texto = this.value.trim();

    if (texto.length < 2) {
        limpiarLista(listaDestinatarios, "destinatarios");
        actualizarPreview();
        return;
    }

    const response = await fetch(`/buscar_destinatarios?q=${encodeURIComponent(texto)}`);
    const destinatarios = await response.json();

    listaDestinatarios.innerHTML = "";
    autocompleteState.destinatarios.index = -1;

    destinatarios.forEach(destinatario => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "list-group-item list-group-item-action";
        item.textContent = destinatario.nombre;

        item.onclick = function () {
            inputDestinatario.value = destinatario.nombre || "";
            inputRutDestinatario.value = destinatario.rut || "";
            inputDireccion.value = destinatario.direccion || "";
            inputComun.value = destinatario.comuna || "";
            inputRegio.value = destinatario.region || "";
            inputTelefonoDestinatario.value = destinatario.telefono || "";
            limpiarLista(listaDestinatarios, "destinatarios");
            actualizarPreview();
        };

        listaDestinatarios.appendChild(item);
    });
});

document.addEventListener("click", function (e) {
    if (!inputDestinatario.contains(e.target) && !listaDestinatarios.contains(e.target)) {
        limpiarLista(listaDestinatarios, "destinatarios");
    }
});

[
    inputRemitente,
    inputCorreoRemitente,
    inputDivision,
    inputCentroCosto
].forEach(el => {
    if (el) {
        el.addEventListener("input", guardarRemitenteEnStorage);
        el.addEventListener("change", guardarRemitenteEnStorage);
    }
});

if (switchMantenerRemitente) {
    switchMantenerRemitente.addEventListener("change", function () {
        guardarRemitenteEnStorage();
    });
}

function actualizarPreview() {
    const get = (id) => document.getElementById(id)?.value?.trim() || "";

    const tipo = get("tipo_envio") || "Domicilio";
    const agencia = get("codigo_agencia");

    document.getElementById("preview_tipo_envio").textContent = tipo.toUpperCase();
    document.getElementById("preview_remitente").textContent = get("remitente") || "Nombre remitente";
    document.getElementById("preview_centro_costo").textContent = get("centro_costo") || "-";
    document.getElementById("preview_correo").textContent = get("correo_remitente") || "-";
    document.getElementById("preview_division").textContent = get("division") || "-";

    document.getElementById("preview_destinatario").textContent = get("destinatario") || "Nombre destinatario";
    document.getElementById("preview_rut").textContent = get("rut_destinatario") || "-";
    document.getElementById("preview_direccion").textContent = get("direccion") || "-";
    document.getElementById("preview_comuna").textContent = get("comuna") || "-";
    document.getElementById("preview_region").textContent = get("region") || "-";
    document.getElementById("preview_telefono").textContent = get("telefono_destinatario") || "-";

    document.getElementById("preview_bultos").textContent = get("bultos") || "0";
    document.getElementById("preview_kilos").textContent = get("kilos") || "0";

    const agenciaBox = document.getElementById("preview_agencia_box");
    const agenciaTexto = document.getElementById("preview_codigo_agencia");

    if (tipo === "Agencia") {
        agenciaBox.style.display = "block";
        agenciaTexto.textContent = agencia || "Codigo de Agencia";
    } else {
        agenciaBox.style.display = "none";
        agenciaTexto.textContent = "-";
    }
}

[
    "tipo_envio",
    "codigo_agencia",
    "remitente",
    "correo_remitente",
    "centro_costo",
    "division",
    "destinatario",
    "rut_destinatario",
    "direccion",
    "comuna",
    "region",
    "telefono_destinatario",
    "bultos",
    "kilos"
].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
        el.addEventListener("input", actualizarPreview);
        el.addEventListener("change", actualizarPreview);
    }
});

restaurarRemitenteDesdeStorage();
actualizarPreview();
