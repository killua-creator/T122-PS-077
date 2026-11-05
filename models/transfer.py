# Holds data for an ownership transfer and an NOC (inter-state migration).

class OwnershipTransfer:
    def __init__(self, transfer_id, vehicle_id, old_owner_id,
                 new_owner_id, sale_date, transfer_date, transfer_fee):
        """
        transfer_id:   unique ID e.g. "TRF001"
        vehicle_id:    registration mark
        old_owner_id:  previous owner's ID
        new_owner_id:  new owner's ID
        sale_date:     string "YYYY-MM-DD" — date the vehicle was sold
        transfer_date: string "YYYY-MM-DD" — date transfer was applied at RTO
        transfer_fee:  total fee charged including any delay penalty
        """
        self.transfer_id   = transfer_id
        self.vehicle_id    = vehicle_id
        self.old_owner_id  = old_owner_id
        self.new_owner_id  = new_owner_id
        self.sale_date     = sale_date
        self.transfer_date = transfer_date
        self.transfer_fee  = transfer_fee
        self.status        = "COMPLETED"

    def __str__(self):
        return (f"Transfer({self.transfer_id}, {self.vehicle_id}, "
                f"{self.old_owner_id} → {self.new_owner_id})")


class NOC:
    def __init__(self, noc_id, vehicle_id, issue_date,
                 road_tax_paid, refund_amount):
        """
        noc_id:         unique ID e.g. "NOC001"
        vehicle_id:     registration mark
        issue_date:     string "YYYY-MM-DD"
        road_tax_paid:  total road tax paid when vehicle was first registered
        refund_amount:  how much the old state will refund (calculated at issue)
        """
        self.noc_id        = noc_id
        self.vehicle_id    = vehicle_id
        self.issue_date    = issue_date
        self.road_tax_paid = road_tax_paid
        self.refund_amount = refund_amount

        # Status
        self.status           = "ISSUED"    # "ISSUED", "UTILISED", "EXPIRED"
        self.utilised_date    = None        # set when confirmation arrives
        self.refund_released  = False       # True when refund is actually paid

    def __str__(self):
        return (f"NOC({self.noc_id}, {self.vehicle_id}, "
                f"refund=Rs {self.refund_amount}, {self.status})")