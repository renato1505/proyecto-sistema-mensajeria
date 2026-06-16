def html_escape(texto):
    return (
        str(texto or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def email_shell_html(titulo, subtitulo, contenido, color="#111827"):
    return f"""
    <!doctype html>
    <html>
    <body style="margin:0;padding:0;background:#f3f5f7;font-family:Arial,Helvetica,sans-serif;color:#161a1f;">
      <div style="max-width:720px;margin:0 auto;padding:28px 18px;">
        <div style="background:{color};color:#ffffff;border-radius:10px 10px 0 0;padding:22px 24px;">
          <div style="font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#f8e5b8;">{html_escape(subtitulo)}</div>
          <div style="font-size:22px;font-weight:900;margin-top:6px;">{html_escape(titulo)}</div>
          <div style="width:72px;height:3px;background:#d9b66b;margin-top:14px;"></div>
        </div>
        <div style="background:#ffffff;border:1px solid #d9dee5;border-top:0;border-radius:0 0 10px 10px;padding:24px;">
          {contenido}
          <p style="margin:22px 0 0;color:#667085;font-size:13px;line-height:1.45;">
            Equipo de Mensajeria<br>
            L'Oreal
          </p>
        </div>
      </div>
    </body>
    </html>
    """


def dato_html(etiqueta, valor):
    return (
        "<div style=\"padding:10px 0;border-bottom:1px solid #eef2f6;\">"
        f"<div style=\"color:#667085;font-size:12px;font-weight:800;\">{html_escape(etiqueta)}</div>"
        f"<div style=\"color:#111827;font-size:14px;font-weight:700;margin-top:3px;\">{html_escape(valor or 'No informado')}</div>"
        "</div>"
    )


def primer_nombre(nombre_completo, respaldo=""):
    partes = str(nombre_completo or "").strip().split()
    return partes[0] if partes else respaldo


def tabla_of_html(envios):
    filas = []
    for envio in envios[:12]:
        filas.append(
            "<tr>"
            f"<td>{html_escape(envio.e_destinatario)}</td>"
            f"<td>{html_escape(envio.e_comuna)}</td>"
            f"<td><strong>{html_escape(envio.e_orden_flete)}</strong></td>"
            "</tr>"
        )

    if len(envios) > 12:
        filas.append(
            "<tr>"
            f"<td colspan=\"3\">Y {len(envios) - 12} envio(s) mas en el Excel adjunto.</td>"
            "</tr>"
        )

    return "".join(filas)


def correo_funcionario_html(lote, remitente, envios, fecha_texto):
    contenido = f"""
        <p style="margin:0 0 14px;font-size:16px;">Hola {html_escape(remitente)},</p>
        <p style="margin:0 0 18px;color:#344054;line-height:1.45;">
          Tus envios ya fueron procesados por Mensajeria y cuentan con orden de flete.
        </p>

        <div style="display:block;background:#f8fafb;border:1px solid #e8ebef;border-radius:8px;padding:16px;margin-bottom:18px;">
          <div style="font-size:12px;color:#667085;font-weight:800;text-transform:uppercase;">Resumen</div>
          <div style="font-size:22px;font-weight:900;margin-top:4px;">{len(envios)} envio(s)</div>
          <div style="color:#667085;margin-top:4px;">Lote: {html_escape(lote)}</div>
          <div style="color:#667085;">Fecha: {html_escape(fecha_texto)}</div>
        </div>

        <table style="width:100%;border-collapse:collapse;margin:0 0 18px;">
          <thead>
            <tr>
              <th align="left" style="padding:10px;border-bottom:1px solid #d9dee5;background:#eef1f4;">Destinatario</th>
              <th align="left" style="padding:10px;border-bottom:1px solid #d9dee5;background:#eef1f4;">Comuna</th>
              <th align="left" style="padding:10px;border-bottom:1px solid #d9dee5;background:#eef1f4;">Orden de flete</th>
            </tr>
          </thead>
          <tbody>
            {tabla_of_html(envios)}
          </tbody>
        </table>

        <p style="margin:0;color:#344054;line-height:1.45;">
          Adjuntamos un Excel con el detalle completo para tu respaldo.
        </p>
    """
    return email_shell_html("Tus envios fueron procesados", "L'Oreal Mensajeria", contenido)


def correo_respaldo_mensajeria_html(lote, envios):
    filas = "".join(
        "<tr>"
        f"<td style=\"padding:9px;border-bottom:1px solid #eef2f6;\">{html_escape(envio.e_remitente)}</td>"
        f"<td style=\"padding:9px;border-bottom:1px solid #eef2f6;\">{html_escape(envio.e_destinatario)}</td>"
        f"<td style=\"padding:9px;border-bottom:1px solid #eef2f6;\"><strong>{html_escape(envio.e_orden_flete)}</strong></td>"
        "</tr>"
        for envio in envios[:14]
    )
    if len(envios) > 14:
        filas += f"<tr><td colspan=\"3\" style=\"padding:9px;color:#667085;\">Y {len(envios) - 14} envio(s) mas en el Excel adjunto.</td></tr>"

    contenido = f"""
        <p style="margin:0 0 16px;color:#344054;line-height:1.45;">
          Respaldo interno del lote procesado. Este correo es para control operativo de Mensajeria.
        </p>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px;">
          <div style="background:#f8fafb;border:1px solid #e8ebef;border-radius:8px;padding:14px;">
            <div style="color:#667085;font-size:12px;font-weight:800;">Lote</div>
            <div style="font-size:16px;font-weight:900;margin-top:4px;">{html_escape(lote)}</div>
          </div>
          <div style="background:#f8fafb;border:1px solid #e8ebef;border-radius:8px;padding:14px;">
            <div style="color:#667085;font-size:12px;font-weight:800;">Total</div>
            <div style="font-size:16px;font-weight:900;margin-top:4px;">{len(envios)} envio(s)</div>
          </div>
        </div>
        <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
          <thead>
            <tr>
              <th align="left" style="padding:9px;background:#eef1f4;border-bottom:1px solid #d9dee5;">Remitente</th>
              <th align="left" style="padding:9px;background:#eef1f4;border-bottom:1px solid #d9dee5;">Destinatario</th>
              <th align="left" style="padding:9px;background:#eef1f4;border-bottom:1px solid #d9dee5;">OF</th>
            </tr>
          </thead>
          <tbody>{filas}</tbody>
        </table>
        <p style="margin:0;color:#667085;">Se adjunta Excel con el lote completo para respaldo.</p>
    """
    return email_shell_html("Respaldo interno de lote", "Control Mensajeria", contenido, "#111827")


def correo_destinatario_html(envio):
    saludo = primer_nombre(envio.e_destinatario, "Hola")
    saludo_texto = f"Hola {saludo}," if saludo != "Hola" else "Hola,"
    contenido = f"""
        <p style="margin:0 0 14px;font-size:16px;font-weight:800;color:#111827;">
          {html_escape(saludo_texto)}
        </p>
        <p style="margin:0 0 16px;color:#344054;line-height:1.5;">
          Te informamos que Mensajeria L'Oreal gestiono un envio a tu nombre mediante Starken.
        </p>
        <div style="background:#f8fafb;border:1px solid #e8ebef;border-radius:8px;padding:16px;margin-bottom:16px;">
          {dato_html("Remitente", envio.e_remitente)}
          {dato_html("Orden de flete", envio.e_orden_flete)}
          {dato_html("Direccion de entrega", envio.e_direccion)}
          {dato_html("Comuna / Region", f"{envio.e_comuna} / {envio.e_region or 'No informada'}")}
          {dato_html("Telefono registrado", envio.e_telefono_destinatario)}
          {dato_html("Observacion", envio.e_observacion)}
        </div>
        <p style="margin:0 0 12px;color:#344054;line-height:1.5;">
          Puedes revisar el seguimiento en Starken ingresando la orden de flete en:
          <a href="https://www.starken.cl/seguimiento" style="color:#047857;font-weight:800;">https://www.starken.cl/seguimiento</a>
        </p>
        <p style="margin:0;color:#344054;line-height:1.5;">
          Si algun dato de entrega no corresponde, por favor comunicate directamente con
          <a href="mailto:mensajeria.alcantara@loreal.com" style="color:#111827;font-weight:800;">mensajeria.alcantara@loreal.com</a>.
        </p>
    """
    return email_shell_html("Tienes un envio en curso", "Notificacion de entrega", contenido, "#0f5132")


def correo_eliminacion_historico_html(total, detalle_filtros, fecha_respaldo):
    filtros_html = "".join(
        f"<li style=\"margin-bottom:6px;\">{html_escape(linea.replace('- ', '', 1))}</li>"
        for linea in detalle_filtros.splitlines()
        if linea.strip()
    )
    return f"""
    <!doctype html>
    <html>
    <body style="margin:0;padding:0;background:#fff7f7;font-family:Arial,Helvetica,sans-serif;color:#161a1f;">
      <div style="max-width:720px;margin:0 auto;padding:28px 18px;">
        <div style="background:#991b1b;color:#ffffff;border-radius:10px 10px 0 0;padding:22px 24px;">
          <div style="font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#fee2e2;">Respaldo de eliminacion</div>
          <div style="font-size:22px;font-weight:900;margin-top:6px;">Historico eliminado</div>
          <div style="width:72px;height:3px;background:#fecaca;margin-top:14px;"></div>
        </div>
        <div style="background:#ffffff;border:1px solid #fecaca;border-top:0;border-radius:0 0 10px 10px;padding:24px;">
          <p style="margin:0 0 16px;color:#344054;line-height:1.5;">
            Se eliminaron registros del historico del Portal Operativo. El archivo Excel adjunto contiene el respaldo de los datos eliminados.
          </p>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px;">
            <div style="background:#fff1f2;border:1px solid #fecdd3;border-radius:8px;padding:14px;">
              <div style="color:#991b1b;font-size:12px;font-weight:800;">Registros eliminados</div>
              <div style="font-size:22px;font-weight:900;margin-top:4px;">{total}</div>
            </div>
            <div style="background:#fff1f2;border:1px solid #fecdd3;border-radius:8px;padding:14px;">
              <div style="color:#991b1b;font-size:12px;font-weight:800;">Fecha respaldo</div>
              <div style="font-size:15px;font-weight:900;margin-top:4px;">{html_escape(fecha_respaldo)}</div>
            </div>
          </div>
          <div style="background:#f8fafb;border:1px solid #e8ebef;border-radius:8px;padding:16px;">
            <div style="color:#667085;font-size:12px;font-weight:900;text-transform:uppercase;margin-bottom:8px;">Filtros aplicados</div>
            <ul style="margin:0;padding-left:18px;color:#344054;">{filtros_html}</ul>
          </div>
          <p style="margin:20px 0 0;color:#667085;font-size:13px;line-height:1.45;">
            Equipo de Mensajeria<br>
            L'Oreal
          </p>
        </div>
      </div>
    </body>
    </html>
    """
