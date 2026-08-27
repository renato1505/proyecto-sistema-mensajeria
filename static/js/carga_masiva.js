function toggleDetalleCarga(id) {
    const fila = document.getElementById(id);

    if (fila) {
        fila.classList.toggle("d-none");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("revision-carga-form");
    if (!form) {
        return;
    }

    const rows = Array.from(form.querySelectorAll(".carga-main-row"));
    const checks = Array.from(form.querySelectorAll(".carga-row-check"));
    const selectAll = document.getElementById("seleccionarTodasCarga");
    const clearSelection = document.getElementById("limpiarSeleccionCarga");
    const selectedCount = document.getElementById("cantidadSeleccionCarga");
    const modifyCount = document.getElementById("cantidadModificarCarga");
    const bulkActions = Array.from(form.querySelectorAll(".bulk-action"));
    let activeFilter = "todos";

    const rowVisible = (row) => !row.hidden;
    const rowMatches = (row, filter) => {
        if (filter === "revision") return row.dataset.review === "true";
        if (filter === "rut") return row.dataset.missingRut === "true";
        if (filter === "tipo") return row.dataset.missingTipo === "true";
        if (filter === "kilos") return row.dataset.missingKilos === "true";
        return true;
    };

    const updateSelection = () => {
        const selected = checks.filter((checkbox) => checkbox.checked);
        const visibleChecks = rows.filter(rowVisible).map((row) => row.querySelector(".carga-row-check"));
        const visibleSelected = visibleChecks.filter((checkbox) => checkbox.checked);

        selectedCount.textContent = selected.length;
        modifyCount.textContent = selected.length;
        clearSelection.disabled = selected.length === 0;
        bulkActions.forEach((button) => { button.disabled = selected.length === 0; });
        selectAll.checked = visibleChecks.length > 0 && visibleSelected.length === visibleChecks.length;
        selectAll.indeterminate = visibleSelected.length > 0 && visibleSelected.length < visibleChecks.length;
    };

    const applyFilter = (filter) => {
        activeFilter = filter;
        rows.forEach((row) => {
            const visible = rowMatches(row, filter);
            row.hidden = !visible;
            const detail = form.querySelector(`[data-detail-index="${row.dataset.rowIndex}"]`);
            if (detail) {
                detail.hidden = !visible;
            }
        });
        form.querySelectorAll(".quick-filter").forEach((button) => {
            const active = button.dataset.reviewFilter === filter;
            button.classList.toggle("active", active);
            button.setAttribute("aria-pressed", String(active));
        });
        updateSelection();
    };

    form.querySelectorAll(".quick-filter").forEach((button) => {
        button.addEventListener("click", () => applyFilter(button.dataset.reviewFilter));
    });

    checks.forEach((checkbox) => checkbox.addEventListener("change", updateSelection));

    selectAll.addEventListener("change", () => {
        rows.filter(rowVisible).forEach((row) => {
            row.querySelector(".carga-row-check").checked = selectAll.checked;
        });
        updateSelection();
    });

    document.getElementById("seleccionarVisiblesCarga").addEventListener("click", () => {
        rows.filter(rowVisible).forEach((row) => {
            row.querySelector(".carga-row-check").checked = true;
        });
        updateSelection();
    });

    document.getElementById("seleccionarIncompletasCarga").addEventListener("click", () => {
        rows.filter((row) => row.dataset.review === "true").forEach((row) => {
            row.querySelector(".carga-row-check").checked = true;
        });
        updateSelection();
    });

    clearSelection.addEventListener("click", () => {
        checks.forEach((checkbox) => { checkbox.checked = false; });
        updateSelection();
    });

    bulkActions.forEach((button) => {
        button.addEventListener("click", () => {
            const selected = checks.filter((checkbox) => checkbox.checked);
            if (!selected.length) {
                return;
            }

            const sourceId = button.dataset.bulkSource;
            const value = sourceId
                ? document.getElementById(sourceId).value.trim()
                : button.dataset.bulkValue;
            if (!value) {
                document.getElementById(sourceId).focus();
                return;
            }

            document.getElementById("campoMasivo").value = button.dataset.bulkField;
            document.getElementById("valorMasivo").value = value;
            form.action = "/aplicar_cambio_masivo_carga";
            form.requestSubmit();
        });
    });

    applyFilter(activeFilter);
});
