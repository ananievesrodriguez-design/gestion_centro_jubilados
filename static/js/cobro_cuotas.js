/* static/js/cobro_cuotas.js */

document.addEventListener('DOMContentLoaded', function () {
    const formCobro = document.getElementById('formCobroCuota');
    const tipoConcepto = document.getElementById('tipo_concepto');
    const fechaCobro = document.getElementById('fecha_cobro');
    const inputMonto = document.getElementById('monto');
    const inputPeriodo = document.getElementById('periodo');
    const ayudaMonto = document.getElementById('monto_ayuda');

    // Salir si los elementos no están en el DOM actual
    if (!tipoConcepto || !inputMonto || !ayudaMonto) {
        return;
    }

    // Leer valores parametrizados desde los data-attributes del formulario (o usar fallback seguro)
    const VALOR_MENSUAL = parseFloat(formCobro?.dataset.valorMensual || 200);
    const VALOR_ANUAL_PROMO = parseFloat(formCobro?.dataset.valorAnualPromo || 1500);
    const VALOR_ANUAL_REGULAR = parseFloat(formCobro?.dataset.valorAnualRegular || 2000);
    const VALOR_INSCRIPCION = parseFloat(formCobro?.dataset.valorInscripcion || 2000);

    const mesesNombres = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ];

    function actualizarReglas() {
        const fechaVal = (fechaCobro && fechaCobro.value) 
            ? new Date(fechaCobro.value + "T00:00:00") 
            : new Date();
            
        const mes = fechaVal.getMonth() + 1; // 1 a 12
        const anio = fechaVal.getFullYear();
        const seleccion = tipoConcepto.value;

        if (seleccion === 'inscripcion') {
            inputMonto.value = VALOR_INSCRIPCION;
            if (inputPeriodo) inputPeriodo.value = `Inscripción ${anio}`;
            ayudaMonto.innerText = `Inscripción institucional vigente: $${VALOR_INSCRIPCION}`;
        } else if (seleccion === 'cuota_anual') {
            // Regla: 1° semestre hasta junio valor promocional, 2° semestre regular
            if (mes <= 6) {
                inputMonto.value = VALOR_ANUAL_PROMO;
                ayudaMonto.innerText = `Pago Anual ${anio} (Beneficio 1° semestre hasta Junio): $${VALOR_ANUAL_PROMO}`;
            } else {
                inputMonto.value = VALOR_ANUAL_REGULAR;
                ayudaMonto.innerText = `Pago Anual ${anio} (2° semestre desde Julio): $${VALOR_ANUAL_REGULAR}`;
            }
            if (inputPeriodo) inputPeriodo.value = `Anual ${anio}`;
        } else if (seleccion === 'cuota_mensual') {
            inputMonto.value = VALOR_MENSUAL;
            if (inputPeriodo) inputPeriodo.value = `${mesesNombres[mes - 1]} ${anio}`;
            ayudaMonto.innerText = `Cuota mensual establecida: $${VALOR_MENSUAL}`;
        } else {
            ayudaMonto.innerText = "Importe libre / editable.";
        }
    }

    tipoConcepto.addEventListener('change', actualizarReglas);
    if (fechaCobro) {
        fechaCobro.addEventListener('change', actualizarReglas);
    }

    // Ejecución inicial para fijar los valores por defecto
    actualizarReglas();
});