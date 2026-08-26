function toggleDetalle(id) {
    const fila = document.getElementById(id);

    if (fila) {
        fila.classList.toggle("d-none");
    }
}

document.querySelectorAll(".file-upload-input").forEach((input) => {
    input.addEventListener("change", () => {
        const nombre = input.files && input.files.length
            ? input.files[0].name
            : "Ningún archivo seleccionado";
        const salida = document.getElementById(input.getAttribute("aria-describedby").split(" ")[0]);

        if (salida) {
            salida.textContent = nombre;
        }
    });
});
