/* static/js/caja.js */

$(document).ready(function() {
    if ($('#tablaCaja').length) {
        $('#tablaCaja').DataTable({
            language: {
                search: "",
                searchPlaceholder: "Buscar por concepto, comprobante...",
                lengthMenu: "Mostrar _MENU_ movimientos",
                info: "Mostrando _START_ a _END_ de _TOTAL_ movimientos",
                infoEmpty: "Mostrando 0 movimientos",
                infoFiltered: "(filtrado de _MAX_ totales)",
                zeroRecords: "No se encontraron movimientos registrados",
                paginate: {
                    first: "Primero",
                    last: "Último",
                    next: "Siguiente",
                    previous: "Anterior"
                }
            },
            pageLength: 25,
            order: [[0, 'desc']] // Ordenar por fecha descendente
        });
    }

    // Sugerencias de categorías rápidas según el tipo seleccionado
    const selectTipo = document.getElementById('modalTipoMovimiento');
    const inputCategoria = document.getElementById('modalCategoria');

    if (selectTipo && inputCategoria) {
        selectTipo.addEventListener('change', function() {
            if (this.value === 'Egreso') {
                inputCategoria.value = 'Servicios / Mantenimiento';
            } else {
                inputCategoria.value = 'Donación / Varios';
            }
        });
    }
});