/* static/js/padron.js */

$(document).ready(function() {
    // Inicialización del DataTables para el Padrón de Socios
    if ($('#tablaSocios').length) {
        $('#tablaSocios').DataTable({
            language: {
                search: "",
                searchPlaceholder: "Buscar socio, DNI, nro...",
                lengthMenu: "Mostrar _MENU_ socios",
                info: "Mostrando _START_ a _END_ de _TOTAL_ socios",
                infoEmpty: "Mostrando 0 socios",
                infoFiltered: "(filtrado de _MAX_ totales)",
                zeroRecords: "No se encontraron socios que coincidan",
                paginate: {
                    first: "Primero",
                    last: "Último",
                    next: "Siguiente",
                    previous: "Anterior"
                }
            },
            pageLength: 20,
            order: [[1, 'asc']]
        });
    }
});