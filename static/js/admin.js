document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("adminUserSearch");
    const areaFilter = document.getElementById("adminAreaFilter");
    const roleFilter = document.getElementById("adminRoleFilter");
    const statusFilter = document.getElementById("adminStatusFilter");
    const cards = Array.from(document.querySelectorAll("[data-user-card]"));
    const emptyState = document.getElementById("adminUserFilterEmpty");

    if (!searchInput || !cards.length) return;

    function matchesStatus(card, status) {
        if (!status) return true;
        if (status === "temporal") return card.dataset.temporal === "1";
        if (status === "sin_acceso") return card.dataset.access === "0";
        return card.dataset.status === status;
    }

    function applyFilters() {
        const search = searchInput.value.trim().toLowerCase();
        const area = areaFilter ? areaFilter.value : "";
        const role = roleFilter ? roleFilter.value : "";
        const status = statusFilter ? statusFilter.value : "";
        let visible = 0;

        cards.forEach(function (card) {
            const matchesSearch = !search || (card.dataset.search || "").toLowerCase().includes(search);
            const matchesArea = !area || card.dataset.area === area;
            const matchesRole = !role || card.dataset.role === role;
            const matches = matchesSearch && matchesArea && matchesRole && matchesStatus(card, status);

            card.hidden = !matches;
            if (matches) visible += 1;
        });

        if (emptyState) {
            emptyState.hidden = visible !== 0;
        }
    }

    [searchInput, areaFilter, roleFilter, statusFilter].forEach(function (control) {
        if (!control) return;
        control.addEventListener("input", applyFilters);
        control.addEventListener("change", applyFilters);
    });
});
