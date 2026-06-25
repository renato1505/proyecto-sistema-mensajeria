function toggleDetalleCarga(id) {
    const fila = document.getElementById(id);

    if (fila) {
        fila.classList.toggle("d-none");
    }
}
