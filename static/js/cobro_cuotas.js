/* static/js/cobro_cuotas.js */

document.addEventListener('DOMContentLoaded', function () {
    const formCobro = document.getElementById('formCobroCuota');
    const tipoConcepto = document.getElementById('tipo_concepto');
    const fechaCobro = document.getElementById('fecha_cobro');
    const mesInicio = document.getElementById('mes_inicio');
    const inputMonto = document.getElementById('monto');
    const inputPeriodo = document.getElementById('periodo');
    const ayudaMonto = document.getElementById('monto_ayuda');
    const ayudaProrrateo = document.getElementById('prorrateo_ayuda');
    const cantidadMeses = document.getElementById('cantidad_meses');
    const cantidadMesesWrapper = document.getElementById('cantidad_meses_wrapper');
    const periodoWrapper = document.getElementById('periodo_wrapper');
    const mesInicioWrapper = document.getElementById('mes_inicio_wrapper');

    if (!tipoConcepto || !inputMonto || !ayudaMonto) {
        return;
    }

    const VALOR_MENSUAL = parseFloat(formCobro.dataset.valorMensual || 200);
    const VALOR_ANUAL_PROMO = parseFloat(formCobro.dataset.valorAnualPromo || 1500);
    const VALOR_ANUAL_REGULAR = parseFloat(formCobro.dataset.valorAnualRegular || 2000);
    const VALOR_INSCRIPCION = parseFloat(formCobro.dataset.valorInscripcion || 2000);

    const mesesNombres = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ];

    if (inputMonto.value) {
        inputMonto.dataset.manuallyEdited = 'true';
    }

    function cantidadPeriodos() {
        if (tipoConcepto.value === 'cuota_anual') return 12;
        if (tipoConcepto.value === 'cuota_semestral') return 6;
        if (tipoConcepto.value === 'cuota_mensual') return 1;
        if (tipoConcepto.value === 'cuota_personalizada') {
            const cantidad = Number.parseInt(cantidadMeses.value, 10);
            return cantidad >= 1 && cantidad <= 12 ? cantidad : 0;
        }
        return 0;
    }

    function actualizarReglas(recalcularMonto = true) {
        const fechaVal = fechaCobro && fechaCobro.value
            ? new Date(`${fechaCobro.value}T00:00:00`)
            : new Date();
        const mesPago = fechaVal.getMonth() + 1;
        const anioPago = fechaVal.getFullYear();
        const inicio = mesInicio && mesInicio.value
            ? new Date(`${mesInicio.value}-01T00:00:00`)
            : fechaVal;
        const mesInicioPago = inicio.getMonth() + 1;
        const anioInicio = inicio.getFullYear();
        const seleccion = tipoConcepto.value;
        const periodos = cantidadPeriodos();
        let montoSugerido = null;

        if (seleccion === 'inscripcion') {
            montoSugerido = VALOR_INSCRIPCION;
            if (inputPeriodo) inputPeriodo.value = `Inscripción ${anioPago}`;
            ayudaMonto.innerText = `Inscripción institucional vigente: $${VALOR_INSCRIPCION}`;
        } else if (seleccion === 'cuota_anual') {
            if (mesPago <= 6) {
                montoSugerido = VALOR_ANUAL_PROMO;
                ayudaMonto.innerText = `Total anual bonificado sugerido: $${VALOR_ANUAL_PROMO}. Puede modificarlo si corresponde.`;
            } else {
                montoSugerido = VALOR_ANUAL_REGULAR;
                ayudaMonto.innerText = `Total anual estándar sugerido: $${VALOR_ANUAL_REGULAR}. Puede modificarlo si corresponde.`;
            }
        } else if (seleccion === 'cuota_semestral') {
            montoSugerido = VALOR_MENSUAL * 6;
            ayudaMonto.innerText = 'Ingrese el total semestral; puede ajustarlo por beneficios.';
        } else if (seleccion === 'cuota_mensual') {
            montoSugerido = VALOR_MENSUAL;
            ayudaMonto.innerText = `Cuota mensual establecida: $${VALOR_MENSUAL}`;
        } else if (seleccion === 'cuota_personalizada') {
            montoSugerido = periodos ? VALOR_MENSUAL * periodos : null;
            ayudaMonto.innerText = 'Ingrese el total abonado por la cantidad de meses elegida.';
        } else {
            ayudaMonto.innerText = "Importe libre / editable.";
        }

        if (cantidadMesesWrapper) {
            const esPersonalizado = seleccion === 'cuota_personalizada';
            cantidadMesesWrapper.classList.toggle('d-none', !esPersonalizado);
            cantidadMeses.required = esPersonalizado;
            cantidadMeses.disabled = !esPersonalizado;
        }
        if (periodoWrapper) {
            const esOtro = seleccion === 'otro';
            periodoWrapper.classList.toggle('d-none', !esOtro);
            inputPeriodo.required = esOtro;
            inputPeriodo.disabled = !esOtro;
            if (esOtro && mesesNombres.some(mes => inputPeriodo.value.toLowerCase().startsWith(mes.toLowerCase()))) {
                inputPeriodo.value = 'Otro importe';
            }
        }
        if (mesInicioWrapper) {
            const requiereMesInicio = periodos > 0;
            mesInicioWrapper.classList.toggle('d-none', !requiereMesInicio);
            mesInicio.required = requiereMesInicio;
            mesInicio.disabled = !requiereMesInicio;
        }

        if (recalcularMonto && !inputMonto.dataset.manuallyEdited && montoSugerido !== null) {
            inputMonto.value = montoSugerido.toFixed(2);
        }

        if (inputPeriodo && periodos && seleccion !== 'otro') {
            inputPeriodo.value = `${mesesNombres[mesInicioPago - 1]} ${anioInicio}`;
        }
        if (ayudaProrrateo) {
            const total = Number.parseFloat(inputMonto.value);
            if (periodos && total > 0) {
                const totalCentavos = Math.round(total * 100);
                const centavosBase = Math.round(totalCentavos / periodos);
                let centavosRestantes = totalCentavos;
                const detalle = [];
                for (let indice = 0; indice < periodos; indice++) {
                    const centavos = indice === periodos - 1
                        ? centavosRestantes
                        : centavosBase;
                    centavosRestantes -= centavos;
                    const indiceMes = mesInicioPago - 1 + indice;
                    const anioMes = anioInicio + Math.floor(indiceMes / 12);
                    const nombreMes = mesesNombres[indiceMes % 12];
                    detalle.push(
                        `${nombreMes} ${anioMes}: $${(centavos / 100).toLocaleString('es-AR', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2
                        })}`
                    );
                }
                ayudaProrrateo.textContent = `Distribución exacta: ${detalle.join(' · ')}`;
            } else {
                ayudaProrrateo.textContent = '';
            }
        }
    }

    tipoConcepto.addEventListener('change', function () {
        delete inputMonto.dataset.manuallyEdited;
        actualizarReglas();
    });
    if (fechaCobro) fechaCobro.addEventListener('change', actualizarReglas);
    if (mesInicio) mesInicio.addEventListener('change', () => actualizarReglas(false));
    if (cantidadMeses) cantidadMeses.addEventListener('input', () => actualizarReglas());
    inputMonto.addEventListener('input', function () {
        inputMonto.dataset.manuallyEdited = 'true';
        actualizarReglas(false);
    });

    actualizarReglas();
});