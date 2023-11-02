import axios from "axios";
import React from "react";

import { apiEndPoint } from "../../config";
import { downloadBlob } from "../../utils";

import "./index.scss";

type propsType = Readonly<{
    ticketId: string,
    deleteTicket: (ticketId: string) => void,
    switchLoading: (status?: boolean) => void,
}>;

export default function TicketBox(props: propsType): React.ReactElement {
    const {
        ticketId,
        deleteTicket,
        switchLoading,
    } = props;

    const downloadTicket = () => {
        switchLoading(true);
        axios.get(
            `${apiEndPoint}/ticket/${ticketId}`,
        ).then((response) => {
            const filePrefix = `${ticketId.split("-", 2).join("-")}-`;
            const fileName = ticketId.replace(filePrefix, "");

            downloadBlob(new File([response.data], fileName), fileName);
        }).finally(() => {
            switchLoading(false);
        });
    }

    return (
        <div className="ticketBox">
            <a className="name" href={`#${ticketId}`}>{ticketId}</a>
            <div className="delete" onClick={() => {deleteTicket(ticketId);}} >Delete</div>
            <div className="download" onClick={downloadTicket} >Download</div>
        </div>
    );
}
