@app.route("/tenders", methods=["GET"])
@require_api_key
def get_tenders():
    """
    Ultra-simplified tender search that just returns tenders without complex filtering.
    """
    try:
        # Get query parameters
        limit = request.args.get('limit', 20, type=int)
        bid_number = request.args.get('bid_number')  # For specific tender lookup
        
        # Define the columns to select
        fields_to_select = (
            "bid_number, item_category, department, organization, quantity, status, "
            "closing_date, tender_amount, city, state, source_url"
        )
        
        # Start building the query
        query = supabase.table('tenders').select(fields_to_select)
        
        # If we have a bid number, filter by it
        if bid_number:
            query = query.eq("bid_number", bid_number)
        
        # Apply limit and execute
        response = query.limit(limit).execute()
        
        # Process the results
        tenders = response.data
        for tender in tenders:
            # Add formatted fields for easier display
            if tender.get('closing_date'):
                tender['formatted_deadline'] = format_date(tender['closing_date'])
            if tender.get('tender_amount'):
                tender['formatted_amount'] = format_amount(tender['tender_amount'])
        
        # Return the results
        return jsonify({
            "success": True, 
            "count": len(tenders), 
            "data": tenders
        })

    except Exception as e:
        print(f"Error in get_tenders: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
