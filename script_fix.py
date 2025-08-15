def get_children_recursive(block_id, depth=0, debug=False):
    if depth >= max_depth:
        return []
    
    all_children = []
    start_cursor = None
    
    try:
        while True:
            if debug and depth < 3:
                print(f"    {'  ' * depth}Fetching children of {block_id[:8]}... at depth {depth}")
            
            response = client.blocks.children.list(
                block_id=block_id,
                page_size=100,
                start_cursor=start_cursor
            )
            
            children = response.get('results', [])
            if debug and depth < 3:
                print(f"    {'  ' * depth}Got {len(children)} children")
            
            for child in children:
                child_id = child.get('id', 'unknown')
                child_type = child.get('type', 'unknown')
                
                # Add metadata about hierarchy
                child['_metadata'] = {
                    'parent_id': block_id,
                    'depth': depth
                }
                all_children.append(child)
                
                if debug and depth < 3:
                    print(f"    {'  ' * depth}  - {child_type} {child_id[:8]} (has_children: {child.get('has_children', False)})")
                
                # Get children recursively, but skip synced blocks
                has_children = child.get('has_children', False)
                block_type = child.get('type')
                is_synced = block_type == 'synced_block'
                
                # UPDATED: Expanded secondary check for API inconsistency
                # Check for API inconsistency - some blocks show has_children=false but actually have children
                container_types = ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                                 'bulleted_list_item', 'numbered_list_item', 'toggle']
                
                needs_secondary_check = (not has_children and 
                                       block_type in container_types and
                                       depth < 3)  # Limit depth for performance
                
                if debug and depth < 3:
                    print(f"    {'  ' * depth}    🔍 Recursion check: has_children={has_children}, is_synced={is_synced}, needs_secondary={needs_secondary_check}")
                
                if (has_children and not is_synced) or needs_secondary_check:
                    try:
                        if debug and depth < 3:
                            check_type = "forced API inconsistency check" if needs_secondary_check else "standard"
                            print(f"    {'  ' * depth}    ⬇️ Recursing into {child_id[:8]} ({check_type})...")
                        
                        # Try to get children
                        grandchildren = get_children_recursive(child_id, depth + 1, debug)
                        
                        if grandchildren:  # Only add if we actually found children
                            all_children.extend(grandchildren)
                            if debug and depth < 3:
                                print(f"    {'  ' * depth}    ✅ Added {len(grandchildren)} grandchildren")
                                if needs_secondary_check:
                                    print(f"    {'  ' * depth}    🎯 SECONDARY CHECK FOUND CHILDREN! (API inconsistency confirmed)")
                        elif needs_secondary_check and debug and depth < 3:
                            print(f"    {'  ' * depth}    ℹ️ Secondary check confirmed no children")
                            
                    except Exception as grandchild_error:
                        # Distinguish between "no children" vs real errors
                        error_msg = str(grandchild_error).lower()
                        if "no children" in error_msg or "404" in error_msg:
                            if debug and depth < 3:
                                print(f"    {'  ' * depth}    ℹ️ No children error (expected for {child_id[:8]})")
                        else:
                            print(f"  ⚠️ Error getting grandchildren of {child_id[:8]} ({child_type}): {grandchild_error}")
                elif debug and depth < 3:
                    print(f"    {'  ' * depth}    ❌ NOT recursing into {child_id[:8]}: has_children={has_children}, is_synced={is_synced}")
            
            if not response.get('has_more', False):
                break
                
            start_cursor = response.get('next_cursor')
            
    except Exception as e:
        print(f"  ❌ Critical error getting children for {block_id[:8]}: {e}")
    
    return all_children